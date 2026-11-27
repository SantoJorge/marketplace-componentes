from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import time
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from apps.catalog.models import Product
from apps.catalog.horizon_cut import cut_name, cut_storage


class Command(BaseCommand):
    help = 'Generate transparent showroom images; use --watch for new or changed photos.'

    def add_arguments(self, parser):
        parser.add_argument('--watch', action='store_true')
        parser.add_argument('--interval', type=int, default=30)
        parser.add_argument('--engine', default=str(Path(os.environ.get('LOCALAPPDATA', '')) / 'HorizonCut' / 'Scripts' / 'python.exe'))

    def handle(self, *args, **options):
        python = Path(options['engine'])
        if not python.is_file():
            raise CommandError('HorizonCut python no encontrado; use --engine')
        if options['interval'] < 10:
            raise CommandError('Intervalo minimo: 10 segundos')
        engine = Path(settings.BASE_DIR) / 'apps/catalog/horizon_cut_engine.py'
        if not engine.is_file():
            raise CommandError('Motor de recorte no encontrado')
        self.stdout.write('HORIZON AUTO CUT: SOLO LECTURA DE PRODUCTOS; ARCHIVOS DERIVADOS')
        if options['watch']:
            self.stdout.write(f'MODO AUTOMATICO ACTIVO: revision cada {options["interval"]} segundos; Ctrl+C para detener')
        try:
            while True:
                close_old_connections()
                try:
                    failures = self.run_batch(python, engine)
                except Exception as exc:
                    if not options['watch']:
                        raise
                    self.stderr.write(f'ERROR DE CICLO: {exc}')
                    failures = 1
                finally:
                    close_old_connections()
                if not options['watch']:
                    if failures:
                        raise CommandError(f'{failures} imagen(es) pendientes o fallidas')
                    return
                time.sleep(options['interval'])
        except KeyboardInterrupt:
            self.stdout.write('HORIZON AUTO CUT DETENIDO')

    def run_batch(self, python, engine):
        storage = cut_storage()
        jobs = []
        failures = 0
        existing = 0
        with tempfile.TemporaryDirectory(prefix='horizon_cut_') as temp:
            root = Path(temp)
            products = Product.objects.exclude(image='').exclude(image__isnull=True).order_by('pk')
            for p in products.iterator():
                try:
                    name = cut_name(p)
                    if not name:
                        raise ValueError('Imagen original no accesible')
                    if storage.exists(name):
                        existing += 1
                        continue
                    source = root / f'{p.pk}_source'
                    output = root / f'{p.pk}_cut.png'
                    with p.image.storage.open(p.image.name, 'rb') as f, source.open('wb') as dest:
                        shutil.copyfileobj(f, dest)
                    jobs.append(dict(id=p.pk, name=name, source=str(source), output=str(output)))
                except Exception as exc:
                    failures += 1
                    self.stderr.write(f'IMAGEN NO DISPONIBLE {p.pk}: {exc}')
            if jobs:
                self.stdout.write(f'PROCESANDO {len(jobs)} RECORTES NUEVOS O ACTUALIZADOS')
                manifest = root / 'jobs.json'
                manifest.write_text(json.dumps(jobs, ensure_ascii=True), encoding='utf-8')
                subprocess.run([str(python), str(engine), str(manifest)], check=False)
                for job in jobs:
                    output = Path(job['output'])
                    if not output.is_file():
                        failures += 1
                        continue
                    fresh = Product.objects.filter(pk=job['id']).first()
                    if fresh is None or cut_name(fresh) != job['name']:
                        self.stdout.write(f'IMAGEN CAMBIO DURANTE PROCESO: {job["id"]}; se reintentara')
                        failures += 1
                        continue
                    target = Path(storage.path(job['name']))
                    target.parent.mkdir(parents=True, exist_ok=True)
                    # Publish atomically: browsers never receive a partially written PNG.
                    with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.hz_', suffix='.tmp', delete=False) as f:
                        tmp = Path(f.name)
                        try:
                            with output.open('rb') as source:
                                shutil.copyfileobj(source, f)
                        except Exception:
                            f.close()
                            tmp.unlink(missing_ok=True)
                            raise
                    try:
                        os.replace(tmp, target)
                    finally:
                        tmp.unlink(missing_ok=True)
                    self.stdout.write(f'PUBLICADO: {job["id"]}')
                self.stdout.write(f'CICLO: existentes={existing}, procesados={len(jobs)}, pendientes/fallos={failures}')
            elif failures or not getattr(self, '_reported_idle', False):
                self.stdout.write(f'CICLO: existentes={existing}, nuevos=0, pendientes/fallos={failures}')
                self._reported_idle = True
        return failures
