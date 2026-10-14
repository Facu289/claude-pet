# Claude Pet

Mascota de escritorio para Windows inspirada en Claude. Vive arriba de tus ventanas, camina por la pantalla y hace cosas random. Solo usa la librería estándar de Python (`tkinter` + `ctypes`), no hay nada que instalar.

## Uso

Requiere Windows 10/11 y Python 3.

```
pythonw claude_pet.py
```

o doble clic en `ClaudePet.bat`.

## Qué hace

- Camina por el piso y por arriba de tus ventanas abiertas (las detecta en tiempo real).
- Salta entre ventanas, se sienta en un borde con las patitas colgando y "surfea" una ventana moviéndola un poco.
- Comenta lo que tenés abierto según el título de la ventana.
- Duerme, programa en su laptop, baila, saluda, toma café, te sigue y a veces te lleva el mouse.
- Cuenta chistes de programación de vez en cuando. Habla poco.
- Te saluda según la hora (buen día / buenas tardes / buenas noches, a veces en inglés u otro idioma), al prender la PC y al volver de suspensión.

## Controles

- **Click**: lo molestás. **Arrastrar**: lo agarrás y lo tirás.
- **Click derecho**: menú para pedirle cada actividad.
- Desde el menú podés desactivar que se lleve el mouse o mueva ventanas, y activar **Iniciar con Windows**.

## Ajustes

`PET_SIZE` al principio de `claude_pet.py` cambia el tamaño de la mascota.

## API key de Claude

Esta versión **no usa** la API de Claude, así que no necesita ninguna key.

Si extendés el proyecto con funciones que llamen a la API de Claude (por ejemplo un chat), poné tu key en un archivo llamado **`api_key.txt`** en esta misma carpeta (solo la key, sin nada más), o definí la variable de entorno `ANTHROPIC_API_KEY`.

`api_key.txt` está en el `.gitignore`, así que **nunca se sube a GitHub**. Conseguí tu key en https://console.anthropic.com. No la pegues en el código ni la compartas.
