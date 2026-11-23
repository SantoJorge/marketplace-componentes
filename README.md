
# MarketplaceComponentes

Plataforma web para la compraventa de componentes de computadoras, desarrollada con Python, Django y MySQL.

## Tecnologías

- Python 3.12
- Django 6.1.1
- MySQL
- mysqlclient
- Pillow
- HTML, CSS y JavaScript

## Estructura del proyecto

- `apps/accounts/`: usuarios y autenticación.
- `apps/catalog/`: catálogo y productos.
- `apps/orders/`: carrito, pedidos y operaciones comerciales.
- `apps/management/`: administración del marketplace.
- `config/`: configuración central de Django.
- `templates/`: plantillas HTML.
- `static/`: recursos estáticos.
- `media/`: archivos cargados durante el desarrollo.

## Requisitos

Para trabajar con el proyecto se necesita:

- Python 3.12 instalado.
- Git.
- MySQL para utilizar la base de datos de desarrollo.
- Un editor como Visual Studio o Visual Studio Code.

## 1. Clonar el repositorio

```powershell
git clone https://github.com/SantoJorge/marketplace-componentes.git
```

```powershell
cd marketplace-componentes
```

## 2. Crear el entorno virtual

En Windows PowerShell:

```powershell
py -3.12 -m venv .venv
```

## 3. Instalar dependencias

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 4. Configurar las variables de entorno

Crear el archivo `.env` a partir de `.env.example`:

```powershell
Copy-Item .env.example .env
```

Abrir `.env` y reemplazar los valores de ejemplo.

Cada desarrollador debe utilizar su propia clave de Django y sus credenciales MySQL.

Para generar una clave Django:

```powershell
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copiar la clave generada a `DJANGO_SECRET_KEY` en `.env`.

Nunca compartir ni publicar el archivo `.env`.

## 5. Configurar MySQL

La configuración de ejemplo utiliza:

```dotenv
DJANGO_DB_ENGINE=mysql
MYSQL_DB_NAME=marketplace_componentes_dev
MYSQL_DB_USER=marketplace_dev
MYSQL_DB_PASSWORD=REEMPLAZAR_CON_PASSWORD_LOCAL
MYSQL_DB_HOST=127.0.0.1
MYSQL_DB_PORT=3306
```

Crear una base de datos local de desarrollo en MySQL:

```sql
CREATE DATABASE IF NOT EXISTS marketplace_componentes_dev
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

Crear un usuario MySQL de desarrollo con una contraseña segura y concederle permisos solamente sobre esa base.

Las credenciales del archivo `.env` deben coincidir con las del usuario MySQL creado.

No utilizar la base principal ni las credenciales de otro desarrollador.

### Alternativa: SQLite

Para trabajar localmente con SQLite, modificar en `.env`:

```dotenv
DJANGO_DB_ENGINE=sqlite
```

SQLite y MySQL tienen comportamientos diferentes, especialmente en las operaciones concurrentes.

Las pruebas específicas de concurrencia deben realizarse con MySQL.

## 6. Ejecutar migraciones

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

## 7. Verificar la configuración

```powershell
.\.venv\Scripts\python.exe manage.py check
```

Resultado esperado:

```text
System check identified no issues (0 silenced).
```

## 8. Crear un administrador

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

## 9. Iniciar el servidor

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Abrir en el navegador:

- Catálogo: http://127.0.0.1:8000/
- Cuentas: http://127.0.0.1:8000/cuenta/
- Gestión: http://127.0.0.1:8000/gestion/
- Administración Django: http://127.0.0.1:8000/admin/

## 10. Datos de demostración

El repositorio contiene `cargar_150_productos.py`, una herramienta para preparar un catálogo de demostración.

Su ejecución sin `--apply` permite previsualizar la operación:

```powershell
.\.venv\Scripts\python.exe cargar_150_productos.py
```

La importación con escritura exige una base MySQL de desarrollo y autorizaciones adicionales.

No ejecutar la importación sobre bases de datos reales ni compartidas sin revisar previamente su configuración.

## 11. Pruebas

Verificación general:

```powershell
.\.venv\Scripts\python.exe manage.py check
```

Algunas pruebas de concurrencia CR-12 requieren una base MySQL aislada y una configuración específica.

No ejecutar indiscriminadamente todas las pruebas contra una base de datos con información importante.

## Seguridad y colaboración

- No subir `.env`.
- No publicar contraseñas ni claves privadas.
- No subir la carpeta `.venv`.
- No subir respaldos de bases de datos.
- Trabajar con datos y credenciales de desarrollo.
- Revisar los cambios antes de cada commit.
- Coordinar las modificaciones de archivos compartidos.

## Repositorio oficial

https://github.com/SantoJorge/marketplace-componentes
