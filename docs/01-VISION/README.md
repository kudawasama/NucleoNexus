# Visión y Filosofía del Proyecto

## El Problema

Los LLMs grandes (70B+, 100B+) requieren hardware especializado (múltiples GPUs, 100GB+ de RAM) que no está al alcance de la mayoría. Sus capacidades son impresionantes pero inaccesibles sin conexión a internet o sin pagar APIs.

Los LLMs pequeños (0.5B - 3B) caben en cualquier PC, incluso en una Raspberry Pi. Pero solos, son limitados: alucinan, no siguen instrucciones complejas, tienen conocimiento limitado.

## La Solución: Inteligencia por Arquitectura, no por Tamaño

La premisa del proyecto es que **un sistema bien diseñado + un modelo pequeño** puede superar a **un modelo grande solo**.

| Componente | Rol | Equivalente |
|---|---|---|
| **LLM pequeño** (Qwen 0.5B) | Genera texto, sigue formatos | Corteza del lenguaje |
| **Memoria semántica** | Almacena hechos y conocimiento | Hipocampo |
| **Motor simbólico** | Reconoce intenciones, ejecuta lógica exacta | Corteza prefrontal |
| **Skills / Acciones** | Ejecuta tareas concretas (clima, calculadora) | Corteza motora |
| **Context Builder** | Inyecta contexto relevante antes de cada respuesta | Atención selectiva |

## Principios Fundamentales

### 1. El modelo no necesita saberlo todo
El modelo no debe almacenar conocimiento en sus pesos. Debe **consultar la memoria** cuando necesite un hecho. Esto se logra con RAG (Retrieval-Augmented Generation) y la infraestructura de memoria de Nexus.

### 2. Las respuestas exactas no necesitan un LLM
Saludos, hora, cálculos matemáticos, estado del sistema — todo eso lo maneja el motor simbólico en milisegundos, sin alucinar, sin consumo de GPU.

### 3. El LLM es para lo que requiere razonamiento
Preguntas abiertas, explicaciones, resúmenes — ahí entra el LLM. Pero incluso en esos casos, se le inyecta contexto de memoria para que no tenga que inventar.

### 4. El sistema aprende de cada interacción
Cada conversación extrae hechos y los almacena. Con el tiempo, el sistema sabe más sin necesidad de un modelo más grande.

### 5. La estructura de pensamiento evita la alucinación
Técnicas como ReAct fuerzan al modelo a "pensar paso a paso" antes de responder, reduciendo drásticamente las alucinaciones incluso en modelos pequeños.

## La Meta Final

Un asistente de IA que:
- Corre completamente local (sin internet, sin APIs)
- Usa un modelo de 500MB - 3B
- Aprende de cada interacción
- Responde desde memoria cuando puede
- Razona con el LLM cuando necesita
- Se vuelve más inteligente con el uso

Sin necesidad de:
- GPUs costosas
- Conexión a internet
- APIs pagadas
- Modelos de 100B+
