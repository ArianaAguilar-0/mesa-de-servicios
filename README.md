# Mesa de Servicio

Sistema web para registrar, asignar y dar seguimiento a las solicitudes de soporte técnico de la universidad.

## Requisitos

- Python 3.10 o superior

## Instalación (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> Si PowerShell no permite activar el entorno, ejecute una sola vez:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## Ejecución

```powershell
python -m solicitudes.app
```

Abra http://127.0.0.1:5000 en el navegador. 

Para detener el sistema: `Ctrl + C`

## Pruebas

```powershell
python -m pytest -v
```
Debe mostrar todas las pruebas en estado `PASSED`.