# ESP - Integración de servicios especializados

Este laboratorio implementa una aplicación de "Lectura Asistida" que recibe una fotografía, reconoce el texto que contiene, lo traduce al español y genera una versión hablada. La solución integra Amazon Rekognition, Amazon Translate y Amazon Polly mediante Lambda functions conectadas por eventos de Amazon S3.

La infraestructura se configura desde AWS Management Console, con la interfaz en inglés. Una plantilla de AWS CloudFormation despliega el sitio, la API y los recursos base, mientras que las interacciones con los servicios especializados deben completarse y verificarse durante el laboratorio.

## Resultados esperados

Al completar el laboratorio, el estudiante podrá:

1. Integrar servicios especializados mediante AWS Lambda y el SDK Boto3
2. Interpretar una respuesta de reconocimiento de texto y transformarla en la entrada de otro servicio
3. Traducir texto mediante detección automática del idioma de origen
4. Generar y almacenar audio a partir de una respuesta de síntesis de voz
5. Conectar etapas de procesamiento mediante eventos S3 con filtros por prefijo
6. Construir permisos IAM según las operaciones y los recursos utilizados por cada función
7. Mantener la relación entre entradas, resultados intermedios y salidas de una misma solicitud
8. Diagnosticar fallas de integración y comprobar el funcionamiento de una cadena de procesamiento

## Preparación previa

Antes del laboratorio:

- Confirme que su cuenta AWS personal se encuentra operativa y que su identidad administrativa de uso regular está protegida con MFA
- Confirme que el role `TEL351-Evaluator` conserva la configuración de confianza utilizada en ICC y SAP, con su RUT normalizado como External ID y la managed policy `ReadOnlyAccess`
- Descargue la [plantilla CloudFormation](infrastructure.yaml) y las [imágenes de prueba](images/) proporcionadas como material del laboratorio. Para descargar la plantilla desde GitHub, abra el archivo y utilice **Download raw file**
- Disponga de un computador para configurar los servicios y, opcionalmente, un teléfono con cámara y acceso a Internet para probar el sitio

> AWS CloudFormation es un servicio que permite crear y administrar recursos de AWS a partir de una plantilla: un archivo que describe los recursos necesarios, su configuración y sus relaciones. Al desplegar la plantilla, CloudFormation crea esos recursos en la cuenta y los agrupa en un conjunto denominado *stack*, que posteriormente puede eliminarse desde el mismo servicio. En este laboratorio se utilizará una plantilla preparada; no es necesario conocer su sintaxis ni modificarla.

## Contexto

Una persona que visita un lugar cuyo idioma desconoce puede encontrar información importante en carteles, avisos o etiquetas sin tener una forma sencilla de interpretarla. Copiar manualmente ese texto a un traductor puede ser difícil cuando utiliza un alfabeto que la persona no conoce. Además, leer la traducción en la pantalla no siempre es la forma más cómoda de acceder al mensaje.

El sistema permite tomar una fotografía o seleccionar una imagen y obtener su contenido en español, tanto escrito como hablado. La persona no necesita identificar previamente el idioma: el sistema reconoce los caracteres de la imagen y luego determina el idioma del texto para traducirlo. El audio se genera a partir de esa traducción, no del texto original.

Cada fotografía inicia una solicitud independiente. El sitio muestra la imagen y los resultados a medida que están disponibles, de modo que se pueda revisar qué texto fue reconocido antes de interpretar la traducción. Si la imagen no contiene texto reconocible, el sistema debe informarlo y detener esa solicitud.

El reconocimiento admite texto en inglés, árabe, ruso, alemán, francés, italiano, portugués y español. La detección automática del idioma ocurre después de extraer el texto y no amplía los alfabetos que puede reconocer Rekognition. Para este laboratorio se utilizarán textos impresos breves, con buena iluminación y sin composiciones de varias columnas.

## Actividad

### 1. Establecer la identidad y la Región

1. Ingrese a AWS Management Console con su identidad administrativa de uso regular
2. Seleccione **US East (N. Virginia)** y compruebe que la Región sea `us-east-1`
3. Anote el **AWS account ID** de 12 dígitos para utilizarlo en el sitio de evaluación

> No todos los servicios de AWS están disponibles en todas las regiones. Amazon Translate y Amazon Comprehend, utilizado para detectar automáticamente el idioma del texto, no están disponibles en São Paulo (`sa-east-1`). En este laboratorio se utilizará North Virginia (`us-east-1`), donde están disponibles todos los servicios necesarios, para mantener el procesamiento en una sola Región. Mantenga esta Región para todos los recursos regionales del laboratorio; IAM y CloudFront no requieren seleccionar una Región.

### 2. Desplegar y comprobar la infraestructura base

CloudFormation crea un conjunto de recursos relacionados, denominado *stack*, a partir de una plantilla. La plantilla proporcionada incluye el sitio con HTTPS, la API, los buckets privados y las funciones auxiliares. También crea las tres funciones de procesamiento en Python, con código inicial, variables de entorno y execution roles con permisos básicos para logs.

#### 2.1 Crear el stack

1. Abra **CloudFormation → Stacks → Create stack → With new resources (standard)**
2. Seleccione **Choose an existing template** y **Upload a template file**
3. Cargue el archivo `infrastructure.yaml` descargado previamente y avance con **Next**
4. Utilice `tel351-esp` como **Stack name** y conserve los parámetros de la plantilla
5. Mantenga las demás opciones por omisión y revise el resumen
6. Confirme la autorización para crear recursos IAM cuando la consola lo solicite e inicie el despliegue
7. Espere hasta que el stack indique **CREATE_COMPLETE**

> Si el despliegue falla, revise **Events** para identificar el recurso y la causa antes de volver a intentarlo.

#### 2.2 Abrir el sitio y reconocer las salidas del despliegue

Una vez que el stack indique **CREATE_COMPLETE**, los recursos estarán creados y podrá obtener la dirección del sitio. CloudFormation reúne las direcciones y los nombres de recursos definidos por la plantilla en la pestaña **Outputs**.

1. En **CloudFormation → Stacks**, seleccione el nombre `tel351-esp` para abrir sus detalles
2. Abra la pestaña **Outputs**
3. Identifique las siguientes filas en la columna **Key** y sus valores en **Value**:

   | Key | Uso del valor mostrado en Value |
   | --- | --- |
   | `WebsiteUrl` | Dirección HTTPS del sitio |
   | `ApiUrl` | Dirección de la API |
   | `DataBucketName` | Nombre del bucket de imágenes y resultados |
   | `WebsiteBucketName` | Nombre del bucket de archivos del sitio |

4. Busque la fila `WebsiteUrl` y copie la dirección HTTPS de su columna **Value**
5. Abra esa dirección en una nueva pestaña del navegador
6. Para utilizar el teléfono, abra la misma dirección en su navegador

`WebsiteUrl` es el nombre del dato de salida; la dirección que debe abrirse es el contenido de **Value**. El sitio de Lectura Asistida es distinto del sitio de evaluación del laboratorio.

#### 2.3 Enviar la primera imagen

El sitio permite seleccionar una imagen o tomar una fotografía desde el teléfono. Prepara las imágenes admitidas en formato JPEG y limita el archivo enviado a 5 MB. Si el navegador no puede abrir un formato, seleccione una versión JPEG o PNG.

1. En el sitio, seleccione la imagen de prueba [en inglés](images/english.jpg)
2. Envíe la imagen
3. Regrese a AWS Management Console y abra **S3 → Buckets**
4. Seleccione el bucket cuyo nombre obtuvo en `DataBucketName`
5. Abra `uploads/`, identifique la imagen recién enviada por su fecha **Last modified** y anote su nombre sin la extensión `.jpg`: ese valor corresponde al `requestId`

En este momento solo se comprueba la carga de la imagen. La extracción, la traducción y el audio se incorporarán progresivamente en los siguientes pasos.

> Mantenga el sitio, la API y las funciones auxiliares sin modificaciones. Los buckets deben conservar **Block all public access** y **Object Ownership: Bucket owner enforced**; no es necesario publicar los objetos.

### 3. Analizar el sistema requerido

En **Lambda → Functions**, identifique las tres funciones de procesamiento creadas por la plantilla:

| Función | Servicio especializado | Resultado |
| --- | --- | --- |
| `tel351-esp-extract` | Amazon Rekognition | Texto reconocido en la imagen |
| `tel351-esp-translate` | Amazon Translate | Idioma detectado y traducción al español |
| `tel351-esp-synthesize` | Amazon Polly | Audio de la traducción |

Cada función recibe una notificación de creación de objeto en S3. El evento identifica el bucket y la key; no contiene directamente la imagen ni el texto que debe procesarse. El código inicial interpreta esa notificación y entrega a la función los datos de la solicitud.

La cadena conserva sus entradas y resultados en el bucket indicado por `DATA_BUCKET`:

```text
uploads/<requestId>.jpg
        │
        └─ tel351-esp-extract → Rekognition
                │
                └─ extracted/<requestId>.json
                        │
                        └─ tel351-esp-translate → Translate
                                │
                                └─ translated/<requestId>.json
                                        │
                                        └─ tel351-esp-synthesize → Polly
                                                │
                                                └─ audio/<requestId>.mp3
```

Los nombres que terminan en `/` son prefijos de las keys, no carpetas que deban crearse previamente. El prefijo permite distinguir qué objetos activan cada función. Los archivos bajo `audio/` y `errors/` no deben activar ninguna de las tres funciones.

El código inicial incluye la lectura de eventos, la obtención del `requestId`, la serialización JSON y las utilidades para registrar errores. Complete los bloques indicados sin cambiar los nombres de los campos ni de las keys. Cada etapa debe utilizar los datos que produjo la anterior, no respuestas fijas asociadas a una imagen de prueba.

> Una notificación puede recibirse más de una vez. Conserve el `requestId` y utilice la misma key de salida para esa solicitud, sin agregar el resultado al contenido anterior.

### 4. Implementar el reconocimiento de texto

#### 4.1 Configurar los permisos de extracción

1. Abra `tel351-esp-extract` en **Lambda → Functions**
2. En **Configuration → Environment variables**, identifique `DATA_BUCKET` y compruebe que coincida con `DataBucketName`
3. En **Configuration → Permissions**, abra el execution role
4. Seleccione **Add permissions → Create inline policy**
5. Mediante el editor visual, autorice las siguientes operaciones:

   | Operación | Recursos autorizados |
   | --- | --- |
   | `rekognition:DetectText` | Todos los recursos; la acción no admite restringir por ARN de imagen |
   | `s3:GetObject` | Objetos bajo `uploads/` en el bucket de datos |
   | `s3:PutObject` | Objetos bajo `extracted/` y `errors/` en el bucket de datos |

6. Guarde la policy con el nombre `tel351-esp-extract`

Para restringir operaciones sobre objetos S3, utilice recursos con la forma `arn:aws:s3:::<bucket>/<prefijo>/*`. No agregue permisos de administración del bucket ni policies como `AdministratorAccess` a los execution roles.

#### 4.2 Completar la extracción

Regrese a la función y abra **Code → `lambda_function.py`**. Complete el bloque de extracción a partir del bucket y la key recibidos en el evento.

La implementación debe:

- Invocar `detect_text` utilizando la referencia `Image.S3Object` de la fotografía
- Construir `sourceText` con las detecciones de tipo `LINE`, unidas por saltos de línea y en el orden recibido
- Conservar el `requestId` y guardar el resultado bajo `extracted/<requestId>.json`
- Informar `NO_TEXT` si no se obtuvo texto, sin escribir un resultado bajo `extracted/`
- Informar `TEXT_TOO_LONG` si el texto supera 1.000 caracteres, sin continuar la cadena

Utilice las funciones auxiliares proporcionadas para guardar el resultado y registrar errores. Seleccione **Deploy** al terminar.

El objeto debe conservar esta estructura:

```json
{
  "requestId": "identificador-de-la-solicitud",
  "sourceText": "Texto reconocido en la fotografía"
}
```

> Las detecciones `LINE` ya contienen las palabras. Incorporar también las detecciones `WORD` duplicaría el texto reconocido.

#### 4.3 Conectar la carga de imágenes con la extracción

1. En la función, seleccione **Add trigger** y elija **S3**
2. Seleccione el bucket de datos, no el bucket del sitio web
3. Configure **Event types: All object create events**, **Prefix: `uploads/`** y **Suffix: `.jpg`**
4. Revise la advertencia sobre invocaciones recursivas: la entrada utiliza `uploads/`, mientras que esta función escribe en `extracted/` o `errors/`
5. Agregue el trigger y confirme que S3 quedó autorizado para invocar la función
6. Envíe una nueva imagen desde el sitio y compruebe que aparezca el texto reconocido
7. Inspeccione el JSON correspondiente en S3 y contraste su contenido con la imagen

La traducción y el audio permanecerán pendientes hasta completar las siguientes etapas.

> Después de corregir una función o agregar un trigger, envíe una nueva imagen. Las notificaciones S3 no procesan retroactivamente los objetos almacenados.

#### 4.4 Inspeccionar resultados y errores

El `requestId` permite relacionar una solicitud con sus objetos en S3 y con los registros de sus funciones en CloudWatch Logs.

Cuando el resultado no sea el esperado:

1. Identifique la última etapa que produjo un resultado visible
2. En el bucket de datos, compruebe que exista el objeto que debe activar la siguiente etapa
3. Abra la función correspondiente y revise su trigger y sus permisos
4. Seleccione **Monitor → View CloudWatch logs** y busque el `requestId`
5. Distinga entre una función que no fue invocada, un error de autorización y una respuesta que el código interpretó incorrectamente
6. Corrija el problema, seleccione **Deploy** si modificó el código y envíe una nueva imagen

Las etapas se ejecutan de manera asincrónica. Utilice el `requestId` para seguir una solicitud mientras se completa.

### 5. Implementar la traducción al español

#### 5.1 Configurar los permisos de traducción

1. Abra `tel351-esp-translate` y seleccione **Configuration → Permissions**
2. Siga el enlace al execution role y seleccione **Add permissions → Create inline policy**
3. Mediante el editor visual, autorice las operaciones indicadas a continuación y guarde la policy como `tel351-esp-translate`:

| Operación | Recursos autorizados |
| --- | --- |
| `translate:TranslateText` | Todos los recursos |
| `comprehend:DetectDominantLanguage` | Todos los recursos |
| `s3:GetObject` | Objetos bajo `extracted/` en el bucket de datos |
| `s3:PutObject` | Objetos bajo `translated/` y `errors/` en el bucket de datos |

Las dos operaciones de análisis de texto no admiten restringir el permiso a un ARN de documento. Amazon Translate utiliza Comprehend para determinar el idioma cuando se solicita detección automática; por eso se requieren ambas acciones, aunque el código invoque solamente Translate.

#### 5.2 Completar la traducción

Abra **Code → `lambda_function.py`** en `tel351-esp-translate` y complete el bloque de traducción.

La implementación debe:

- Utilizar `sourceText` del objeto JSON que activó la función
- Invocar `translate_text` con detección automática del idioma de origen y español como destino
- Recuperar el idioma detectado y la traducción desde la respuesta del servicio
- Conservar el `requestId` y el texto original
- Guardar el resultado bajo `translated/<requestId>.json`

Seleccione **Deploy** después de completar el código.

La salida debe tener esta estructura:

```json
{
  "requestId": "identificador-de-la-solicitud",
  "sourceText": "The next train arrives in ten minutes.",
  "sourceLanguage": "en",
  "targetLanguage": "es",
  "translatedText": "El próximo tren llega en diez minutos."
}
```

El ejemplo ilustra el contrato, no una traducción exacta que deba reproducirse. `sourceLanguage` debe contener el código devuelto por Translate, no el valor `auto` utilizado en la solicitud.

El código inicial contempla errores de detección de idioma y de acceso al servicio. Si la detección no tiene confianza suficiente, debe informarse `LANGUAGE_NOT_DETECTED`; no suponga inglés ni reemplace el texto por un mensaje fijo para continuar.

#### 5.3 Conectar y comprobar la traducción

1. Agregue a `tel351-esp-translate` un trigger S3 sobre el bucket de datos
2. Utilice **All object create events**, **Prefix: `extracted/`** y **Suffix: `.json`**
3. Confirme que la función escribe sus resultados en `translated/`, fuera del prefijo que la activa
4. Envíe una nueva imagen desde el sitio
5. Compruebe que se muestre el texto original, su idioma y la traducción al español
6. Repita con una imagen de prueba en otro idioma, sin modificar el código ni seleccionar manualmente el idioma de origen

Compare el resultado de la traducción con el texto reconocido. Una palabra mal extraída puede producir una traducción incorrecta aunque la integración con Translate funcione correctamente.

### 6. Implementar la síntesis de voz

#### 6.1 Configurar los permisos de síntesis

1. Abra `tel351-esp-synthesize` y seleccione **Configuration → Permissions**
2. Siga el enlace al execution role y seleccione **Add permissions → Create inline policy**
3. Mediante el editor visual, autorice las operaciones indicadas a continuación y guarde la policy como `tel351-esp-synthesize`:

| Operación | Recursos autorizados |
| --- | --- |
| `polly:SynthesizeSpeech` | Todos los recursos |
| `s3:GetObject` | Objetos bajo `translated/` en el bucket de datos |
| `s3:PutObject` | Objetos bajo `audio/` y `errors/` en el bucket de datos |

`SynthesizeSpeech` no permite restringir el recurso mediante un ARN de voz. Mantenga el alcance específico de la acción y restrinja por separado los objetos S3 utilizados.

#### 6.2 Completar la generación de audio

La función utiliza la variable de entorno `VOICE_ID`, cuyo valor inicial es `Lupe`, una voz en español compatible con el motor `standard`.

Abra **Code → `lambda_function.py`** en `tel351-esp-synthesize` y complete el bloque de síntesis.

La implementación debe:

- Utilizar `translatedText`, no el texto original, como entrada de `synthesize_speech`
- Obtener la voz desde `VOICE_ID` y utilizar el motor `standard`, texto plano (`TextType: text`) y formato `mp3`
- Leer los bytes de `AudioStream`
- Guardar el audio bajo `audio/<requestId>.mp3`, con `Content-Type: audio/mpeg`

Seleccione **Deploy** después de completar el código.

> `AudioStream` contiene el audio como un flujo de bytes. Debe leerse y almacenarse como contenido binario, no serializarse como JSON.

La estructura inicial valida que el texto no esté vacío ni exceda los 3.000 caracteres admitidos por esta actividad antes de invocar Polly. Si excede ese límite, debe informar `TEXT_TOO_LONG`, sin recortarlo silenciosamente.

#### 6.3 Conectar y comprobar el audio

1. Agregue a `tel351-esp-synthesize` un trigger S3 sobre el bucket de datos
2. Utilice **All object create events**, **Prefix: `translated/`** y **Suffix: `.json`**
3. Compruebe que no existan notificaciones que activen estas funciones por objetos bajo `audio/` o `errors/`
4. Envíe una nueva imagen desde el sitio
5. Espere los resultados de extracción, traducción y síntesis
6. Utilice el reproductor para escuchar el audio y contraste su contenido con la traducción visible
7. En S3, compruebe que el archivo MP3 tenga contenido y el tipo `audio/mpeg`

La reproducción se inicia mediante una acción del usuario. Que el navegador no reproduzca automáticamente el archivo no implica una falla de la síntesis.

### 7. Comprobar el funcionamiento completo

Realice las siguientes pruebas utilizando nuevas solicitudes y conserve sus identificadores para inspeccionar los resultados:

1. **Texto en alfabeto latino:** envíe la imagen de prueba [en inglés](images/english.jpg) o [en francés](images/french.png) y compruebe la cadena completa
2. **Texto en otro alfabeto:** utilice la imagen de prueba [en ruso](images/russian.jpg) y confirme que los caracteres reconocidos se conserven, que se detecte el idioma y que la salida sea texto y audio en español
3. **Imagen sin texto:** envíe la [imagen de prueba sin texto](images/no-text.png) y compruebe que el sitio informe `NO_TEXT`, sin generar traducción ni audio
4. **Solicitudes independientes:** envíe dos imágenes con mensajes distintos y compruebe que cada resultado conserve su `requestId` y corresponda a la fotografía correcta
5. **Fotografía propia:** pruebe el sistema desde el teléfono o cargue una imagen propia con texto breve y legible, sin datos personales ni información confidencial
6. **Texto demasiado extenso:** envíe la [imagen con más de 1.000 caracteres](images/long-text.jpg) y compruebe que se informe `TEXT_TOO_LONG`, sin generar traducción ni audio

La calidad depende de la imagen y de las capacidades de los modelos. Revise las salidas intermedias cuando existan diferencias de reconocimiento o traducción. Las imágenes proporcionadas permiten comprobar la integración antes de atribuir un resultado a una fotografía difícil de interpretar. Para las fotografías propias, prefiera frases completas: una palabra aislada puede ser insuficiente para determinar el idioma con confianza.

Compruebe que el texto reconocido corresponda a la imagen, que la traducción esté en español y que el audio reproduzca esa traducción.

Finalmente, ejecute la evaluación desde el sitio de evaluación del laboratorio y revise sus resultados antes de iniciar la limpieza.

## Evaluación

En cualquier momento del laboratorio puede evaluar la infraestructura y el comportamiento implementado. Cada intento comprueba el estado alcanzado al seguir la guía, incluso si todavía no se ha completado toda la cadena.

1. Ingrese al [sitio de evaluación del laboratorio](https://lab06.shareddomain.link)
2. Complete **AWS account ID** y **RUT normalizado**, sin puntos ni guion y con `k` minúscula
3. Inicie la evaluación y revise el resultado de cada comprobación
4. Corrija la implementación y vuelva a evaluar durante el bloque

La evaluación envía imágenes de prueba mediante la API del sitio y espera los resultados de la cadena; puede tardar algunos minutos. Sus solicitudes aparecen en el resultado del intento para que pueda inspeccionar los objetos correspondientes en S3. Si se interrumpe la consulta, utilice **Consultar evaluación pendiente** para recuperar el resultado del mismo intento.

Las comprobaciones suman 100 puntos y el sitio conserva el historial de intentos asociado al RUT. El acceso a la cuenta utiliza el role `TEL351-Evaluator` configurado previamente.

Realice una evaluación final antes de terminar el bloque. No se solicita un informe ni una entrega separada de código. Mantenga la infraestructura disponible hasta que concluya la evaluación y realice la limpieza después del laboratorio.

## Limpieza posterior

Realice la limpieza después de completar la evaluación, fuera del bloque de clase:

1. Deje de enviar solicitudes y espere a que terminen las que están en curso
2. Elimine los tres triggers S3 agregados durante la actividad
3. En **CloudFormation → tel351-esp → Outputs**, identifique los buckets de datos y del sitio
4. Vacíe ambos buckets mediante **S3 → Buckets → Empty**; esto elimina las imágenes, los resultados intermedios, el audio y los archivos del sitio
5. Elimine las inline policies agregadas a los tres execution roles durante el laboratorio
6. En CloudFormation, seleccione el stack `tel351-esp`, utilice **Delete** y espere a que termine la eliminación
7. Si aparece **DELETE_FAILED**, revise **Events**, resuelva la causa indicada y vuelva a solicitar la eliminación
8. Compruebe que no permanezcan las funciones, los buckets, la API ni los log groups creados exclusivamente para este laboratorio

No elimine `TEL351-Evaluator`, su identidad administrativa ni recursos utilizados en otras actividades. La eliminación de los objetos S3 es definitiva para esta actividad: realícela solamente después de terminar las pruebas y la evaluación.

## Apéndice: Referencia de interacciones con los servicios especializados

Esta referencia resume las operaciones utilizadas en el laboratorio. Los ejemplos emplean nombres genéricos y deben adaptarse a las entradas y salidas de cada función.

### Contratos y resultados de error

Las etapas utilizan el mismo `requestId` recibido desde la base del sistema. Los objetos JSON se guardan en UTF-8 con `Content-Type: application/json`; el audio se almacena como bytes con `Content-Type: audio/mpeg`.

La utilidad de errores del código inicial conserva la etapa y el motivo bajo `errors/<requestId>.json`. El sitio distingue ese resultado de una solicitud que todavía está pendiente:

```json
{
  "requestId": "identificador-de-la-solicitud",
  "stage": "extract",
  "code": "NO_TEXT",
  "message": "No se reconoció texto en la imagen."
}
```

`stage` identifica `extract`, `translate` o `synthesize`. Los códigos `NO_TEXT`, `LANGUAGE_NOT_DETECTED` y `TEXT_TOO_LONG` representan las condiciones descritas en la actividad. Los demás errores se registran como `PROCESSING_ERROR`, con su detalle técnico en CloudWatch Logs. No exponga credenciales ni contenido sensible en los mensajes presentados al usuario.

### Acceso a los servicios mediante Boto3

`boto3.client` permite invocar las operaciones de un servicio. El SDK utiliza las credenciales temporales del execution role de la función; no es necesario incorporar access keys al código.

```python
import boto3

rekognition = boto3.client("rekognition")
translate = boto3.client("translate")
polly = boto3.client("polly")
```

Cada función utiliza los clientes que necesita. Las respuestas son diccionarios de Python; sus campos se consultan mediante el nombre definido por la API.

### Reconocer texto con DetectText

`detect_text` puede recibir la referencia de una imagen almacenada en S3:

```python
response = rekognition.detect_text(
    Image={
        "S3Object": {
            "Bucket": bucket_name,
            "Name": image_key,
        }
    }
)

detections = response.get("TextDetections", [])
```

Cada elemento de `detections` incluye `Type` y `DetectedText`. Analice esos campos para seleccionar las detecciones que forman el texto de salida. Los nombres de los parámetros distinguen mayúsculas y minúsculas: la key de la imagen se entrega como `Name` dentro de `S3Object`.

### Traducir texto con TranslateText

`translate_text` recibe texto y códigos de idioma. El valor `auto` solicita detectar el idioma de origen:

```python
response = translate.translate_text(
    Text=text,
    SourceLanguageCode="auto",
    TargetLanguageCode="es",
)
```

La respuesta contiene `TranslatedText`, `SourceLanguageCode` y `TargetLanguageCode`. El idioma de origen de la respuesta corresponde al detectado por el servicio. Utilice esos resultados para construir el contrato de salida de la etapa.

### Generar audio con SynthesizeSpeech

`synthesize_speech` recibe el texto, la voz, el motor y el formato de salida:

```python
response = polly.synthesize_speech(
    Text=text,
    TextType="text",
    VoiceId=voice_id,
    Engine="standard",
    OutputFormat="mp3",
)

audio_bytes = response["AudioStream"].read()
```

`audio_bytes` contiene datos binarios. No se debe convertir ese contenido a un string ni serializarlo como JSON antes de guardarlo.

### Guardar resultados en S3

`put_object` utiliza `Bucket`, `Key`, `Body` y `ContentType`. Para un archivo binario:

```python
s3 = boto3.client("s3")

s3.put_object(
    Bucket=bucket_name,
    Key=output_key,
    Body=audio_bytes,
    ContentType="audio/mpeg",
)
```

Para guardar JSON se utiliza un documento serializado en UTF-8 y `ContentType="application/json"`. El código inicial incluye utilidades para esa conversión. La key de salida debe corresponder al prefijo de la etapa y conservar el `requestId`.
