# STL Inventory

Local web app for cataloguing, browsing, and managing a large STL file library.

## Quick Start

1. Copy `.env.example` to `.env` and set your drive paths:
   ```
   STL_DRIVE_1=D:/3D STLs
   STL_DRIVE_2=E:/3D STLs
   ```

2. Start everything:
   ```
   docker compose up --build
   ```

3. Open **http://localhost** in your browser.

4. Click **Scan Library** to index your files.

## Structure assumed on disk

```
<drive root>/
  <Creator Name>/
    <Model Name>/
      config.orynt3d      ← parsed automatically
      *.stl / *.3mf
      *.jpg / *.png       ← used as thumbnail
```

## Ports

| Service  | Port |
|----------|------|
| App (nginx) | 80 |
| Backend (FastAPI) | 8000 |
| Frontend (Vite dev) | 3000 |

## Stack

- **Backend**: Python 3.12 + FastAPI + SQLAlchemy + SQLite
- **Frontend**: React 18 + Vite + TypeScript + TailwindCSS
- **Proxy**: nginx
