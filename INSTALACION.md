# Instalar OpenAPU en Windows

## Para utilizar OpenAPU

Descarga siempre el paquete preparado desde:

**[OpenAPU-Windows.zip](https://github.com/KuboServicios/OpenAPU/releases/latest/download/OpenAPU-Windows.zip)**

1. Al terminar la descarga, haz clic derecho sobre `OpenAPU-Windows.zip`.
2. Selecciona **Extraer todo**.
3. Abre la carpeta extraída.
4. Haz doble clic en `INICIAR OPENAPU.cmd`.
5. Mantén abierta la ventana de inicio mientras trabajas.

No necesitas instalar Python, ejecutar comandos ni abrir la carpeta `Aplicacion`.

## Detener OpenAPU

Cierra la ventana negra de inicio. Los proyectos permanecen guardados localmente.

## Actualizar

1. Genera un respaldo desde OpenAPU.
2. Descarga la versión más reciente.
3. Extrae el nuevo paquete en otra carpeta.
4. Abre la versión nueva y restaura el respaldo si corresponde.

No reemplaces archivos dentro de la carpeta `Aplicacion` mientras OpenAPU esté funcionando.

## Problemas habituales

### Aparecen muchos archivos técnicos

Descargaste el código fuente mediante **Code → Download ZIP**. Vuelve a GitHub y descarga `OpenAPU-Windows.zip` desde **Releases**.

### OpenAPU no inicia

Comprueba que extrajiste completamente el ZIP. No ejecutes `INICIAR OPENAPU.cmd` desde la vista de archivos comprimidos.

### El puerto 8767 está ocupado

Cierra otras ventanas de OpenAPU o CodeAPU y vuelve a intentarlo.

### Windows o la empresa impiden abrirlo

No desactives las protecciones del equipo. Solicita revisión al encargado informático e indica que el paquete contiene código Python de fuente abierta y un entorno local integrado.

## Para desarrolladores

El botón **Code → Download ZIP** y `git clone` entregan el código fuente. Esa modalidad requiere Python 3.11 o superior:

```powershell
python -m pip install -r requirements.txt
python server.py --port 8767
```

También puedes abrir `INICIAR OPENAPU.cmd`; si detecta una copia de desarrollo, crea `.venv` y prepara las dependencias.

## Privacidad y soporte

OpenAPU solo escucha en `127.0.0.1`. No adjuntes `openapu.db`, respaldos ni antecedentes de proyectos en un issue público. Para reportar un error utiliza GitHub sin incluir información confidencial.
