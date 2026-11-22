# Formateador y Ordenador para Notion

Script en Python conectado a la API de Notion mediante **GitHub Actions** (sin servidores encendidos ni hosting). Toma notas copiadas en orden inverso (de abajo hacia arriba), agrupa cada explicación con sus respectivos comandos o listas, invierte los bloques para que se lean de arriba hacia abajo y aplica formato nativo de Notion (bloques de código, resaltado *inline* y divisores).

---

## Cómo usar la conexión (Flujo diario)

1. Abre cualquier página o tarjeta de base de datos en Notion (dentro de tu espacio conectado) y añade **`[ORDENAR]`** al título.  
   *Ejemplo:* `Clase 1: Fundamentos de Git [ORDENAR]`
2. Pega el texto desordenado en el cuerpo de la página.
3. Haz clic en tu marcador de **GitHub Actions** guardado en Notion y presiona **Run workflow**.
4. En ~10 segundos, la página se actualizará automáticamente con el contenido ordenado y eliminará la etiqueta `[ORDENAR]` del título.

---

## Tutorial de instalación y conexión

### 1. Crear la integración en Notion
1. Ve a [notion.so/my-integrations](https://www.notion.so/my-integrations) y haz clic en **New integration**.
2. Asígnale un nombre (ej. `Formateador`) y copia el **Internal Integration Secret** (`ntn_...`).
3. En Notion, abre tu página principal o **Base de Datos** -> menú `•••` (esquina superior derecha) -> **Connections** -> selecciona tu integración.  
   *(Todas las subpáginas o tarjetas dentro de esa base de datos heredarán el permiso automáticamente).*

### 2. Estructura del repositorio en GitHub
Crea un repositorio con la siguiente estructura en la raíz:

```text
├── .github/
│   └── workflows/
│       └── formatear.yml
├── formatear.py
└── README.md
```

El archivo `.github/workflows/formatear.yml` debe contener:

```yaml
name: Formatear Notion
on:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  run-script:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install notion-client==2.2.1
      - env:
          NOTION_TOKEN: ${{ secrets.NOTION_TOKEN }}
        run: python formatear.py
```

### 3. Configurar el secreto en GitHub
1. En tu repositorio, ve a **Settings** -> **Secrets and variables** -> **Actions**.
2. Haz clic en **New repository secret**:
   * **Name:** `NOTION_TOKEN`
   * **Secret:** Pega tu token `ntn_...` de Notion.

### 4. Crear acceso directo en Notion (Opcional)
1. Ve a la pestaña **Actions** de tu repositorio -> selecciona **Formatear Notion** en el menú lateral izquierdo y copia la URL del navegador.
2. Pégala en tu página principal de Notion y selecciona **Create bookmark** para tener el disparador a un clic.

---

## Cómo funciona el ordenamiento

* **Inversión por bloques:** Revierte el orden general de los conceptos (de abajo hacia arriba $\rightarrow$ de arriba hacia abajo) conservando el orden interno de cada explicación, comando o lista.
* **Cohesión automática:** Mantiene unidas las líneas que terminan en `:` con sus respectivos comandos o viñetas, y convierte los comandos de terminal en bloques de código `bash`.
* **Protección de estructura:** Ignora encabezados (`H1`–`H3`), divisores, marcadores e imágenes existentes para no alterar el resto de la página.

---

## Ejemplo

### Antes (Texto pegado en Notion)
**Título:** `Apuntes de Git [ORDENAR]`

```text
Check repository status with git status:
git status
Initialize a new repository:
git init
Version control records file changes over time.
```

### Después (Resultado automático en Notion)
**Título:** `Apuntes de Git`

> Version control records file changes over time.
>
> ---
>
> Initialize a new repository:
> ```bash
> git init
> ```
>
> ---
>
> Check repository status with `git status`:
> ```bash
> git status
> ```