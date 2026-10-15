# Pruebas de carga HTTP – Fungi Atlas

## 1. Objetivo

Modificar el script de pruebas HTTP proporcionado en clase para evaluar el comportamiento de los tres servicios Docker de Fungi Atlas: frontend, backend y API LDAP.

Las pruebas permiten identificar la mayor carga observada sin errores y comprobar cómo responden las protecciones configuradas con Nginx y Fail2ban.

## 2. Modificaciones realizadas al script

Se utilizó el archivo original `flood.py` como base y se realizaron las siguientes modificaciones:

- Se permitió indicar la URL de destino, incluyendo host, puerto y ruta.
- Se incorporaron parámetros configurables mediante variables de entorno:
  - `DURATION`: duración de la prueba en segundos.
  - `CONCURRENCY`: cantidad de workers.
  - `REQUESTS_PER_SECOND`: máximo de solicitudes por segundo.
- Se establecieron límites de configuración y tiempos de espera.
- Se modificó el manejo de las rutas para evitar agregar automáticamente una barra `/` al final.
- Se mejoró el reporte para mostrar solicitudes totales, respuestas HTTP 200, respuestas HTTP 429, otros códigos HTTP y errores de conexión o timeout (`000`).
- Se añadieron porcentajes de solicitudes exitosas y no exitosas.

El script se ejecuta desde el equipo anfitrión y permanece fuera de las tres imágenes Docker protegidas.

## 3. Servicios evaluados

| Servicio | URL de prueba |
|---|---|
| Frontend | `http://localhost:5173/` |
| Backend | `http://localhost:3001/` |
| API LDAP | `http://localhost:8000/openapi.json` |

El servicio OpenLDAP también cuenta con protección adicional mediante Fail2ban en el puerto LDAPS 636, correspondiente a la conexión LDAP con TLS. Las pruebas descritas en este documento evalúan las interfaces HTTP, no la carga del protocolo LDAPS.

## 4. Ejecución del script

Requisitos:

- Python 3.
- Servicios Docker de Fungi Atlas en ejecución.
- Acceso HTTP a los puertos de prueba.

Ejemplo para probar el frontend:

```bash
DURATION=10 \
CONCURRENCY=5 \
REQUESTS_PER_SECOND=6 \
python3 attacker/flood.py http://localhost:5173/
```

Para probar el backend:

```bash
DURATION=10 \
CONCURRENCY=5 \
REQUESTS_PER_SECOND=6 \
python3 attacker/flood.py http://localhost:3001/
```

Para probar la API LDAP:

```bash
DURATION=10 \
CONCURRENCY=5 \
REQUESTS_PER_SECOND=6 \
python3 attacker/flood.py http://localhost:8000/openapi.json
```

Se modificó progresivamente el parámetro `REQUESTS_PER_SECOND` para comparar el comportamiento de los servicios.

## 5. Resultados de las pruebas

Las pruebas graduales se realizaron durante 10 segundos, utilizando 5 workers.

| Servicio | Solicitudes/s | Total | HTTP 200 | HTTP 429 | Errores 000 | Éxito |
|---|---:|---:|---:|---:|---:|---:|
| Frontend | 5 | 50 | 50 | 0 | 0 | 100% |
| Frontend | 6 | 60 | 60 | 0 | 0 | 100% |
| Frontend | 7 | 61 | 47 | 5 | 9 | 77.0% |
| Backend | 5 | 50 | 50 | 0 | 0 | 100% |
| Backend | 6 | 60 | 60 | 0 | 0 | 100% |
| Backend | 7 | 61 | 50 | 6 | 5 | 82.0% |
| API LDAP | 5 | 50 | 50 | 0 | 0 | 100% |
| API LDAP | 6 | 60 | 60 | 0 | 0 | 100% |
| API LDAP | 7 | 61 | 48 | 6 | 7 | 78.7% |

## 6. Interpretación de los resultados

Con una carga de 6 solicitudes por segundo, los tres servicios respondieron correctamente al 100% de las solicitudes realizadas.

Al incrementar la carga a 7 solicitudes por segundo comenzaron a aparecer respuestas HTTP 429, que indican que Nginx rechazó solicitudes por exceder los límites configurados.

También se registraron errores de conexión o timeout (`000`), compatibles con interrupciones de conexión durante la prueba. Estos resultados, por sí solos, no demuestran que el servicio haya dejado de funcionar.

Se comprobó posteriormente la recuperación de los servicios mediante solicitudes HTTP.

## 7. Carga observada sin errores

| Servicio | Mayor carga probada sin errores |
|---|---|
| Frontend | 6 solicitudes por segundo |
| Backend | 6 solicitudes por segundo |
| API LDAP | 6 solicitudes por segundo |

**Condiciones:** 10 segundos de duración y 5 workers.

Este valor representa la mayor carga comprobada sin errores durante las pruebas realizadas, no un límite absoluto de capacidad.

## 8. Conclusión

La modificación del script permitió realizar pruebas controladas de carga sobre los tres servicios HTTP de Fungi Atlas.

Se identificó que los tres respondieron sin errores a 6 solicitudes por segundo bajo las condiciones evaluadas. Al aumentar a 7 solicitudes por segundo comenzaron los rechazos y errores de conexión.

Las pruebas permitieron observar el funcionamiento de la limitación de solicitudes de Nginx y complementar la revisión de la protección configurada con Fail2ban.
