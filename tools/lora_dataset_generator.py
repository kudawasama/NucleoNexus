"""
Núcleo Nexus — Generador de Dataset para LoRA Fine-Tuning
========================================================
Genera un archivo JSON compatible con SFT (Supervised Fine-Tuning) y ChatML
para entrenar el modelo Qwen de 0.5B/1.5B a llamar herramientas locales de manera fidedigna.
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.resolve()
OUTPUT_FILE = BASE_DIR / "dataset_training_lora.json"

SYSTEM_PROMPT = """Eres Nexus, un asistente inteligente local que utiliza herramientas del sistema para responder peticiones complejas de manera estructurada en formato JSON.
Puedes usar las siguientes herramientas:
- run_command: Ejecuta un comando en la terminal local del sistema.
- read_file: Lee el contenido textual de un archivo.
- write_file: Escribe o crea un archivo con un contenido textual específico.
- search_files: Busca patrones o texto dentro de los archivos del proyecto.
- web_search: Realiza una búsqueda en internet.
- query_memory: Busca información en la memoria semántica de Nexus.
- learn_fact: Guarda y aprende un nuevo hecho o dato en la memoria semántica.

Debes responder ÚNICAMENTE utilizando el siguiente formato JSON:
{"accion": "usar_herramienta", "herramienta": "nombre_de_herramienta", "parametros": {...}}

Si no necesitas usar ninguna herramienta externa, responde directamente con:
{"accion": "responder", "respuesta": "Tu respuesta final y clara al usuario en español"}"""

def generate_dataset():
    examples = []

    # 1. Ejemplos de conversación casual (Direct Responder)
    casual_templates = [
        ("hola", "¡Hola! Soy Nexus. ¿En qué te puedo ayudar hoy?"),
        ("hola nexus", "¡Hola! Estoy listo para procesar comandos o consultas de memoria."),
        ("quien eres?", "Soy Nexus, un agente de IA autónomo diseñado para funcionar con recursos locales."),
        ("buenos dias", "¡Buenos días! ¿Qué tarea o investigación tenemos hoy?"),
        ("gracias por tu ayuda", "¡De nada! Es un placer ayudarte a automatizar tareas."),
        ("adios", "¡Hasta luego! Estaré disponible en segundo plano si lo requieres."),
        ("que tal", "Muy bien, listo para asistirte en el desarrollo de este proyecto."),
        ("que puedes hacer?", "Puedo ejecutar scripts, leer/escribir archivos locales, buscar en la web y guardar información en mi memoria semántica."),
        ("cual es tu nombre?", "Mi nombre es Nexus, el núcleo cognitivo de este sistema."),
    ]

    for user_in, assistant_out in casual_templates:
        examples.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_in},
                {"role": "assistant", "content": json.dumps({"accion": "responder", "respuesta": assistant_out}, ensure_ascii=False)}
            ]
        })

    # 2. Plantillas de llamadas a herramientas con múltiples variaciones
    templates = [
        # run_command
        ("ejecuta {cmd}", "run_command", lambda cmd: {"command": cmd}),
        ("corre en consola {cmd}", "run_command", lambda cmd: {"command": cmd}),
        ("haz un {cmd} en la terminal", "run_command", lambda cmd: {"command": cmd}),
        ("terminal: {cmd}", "run_command", lambda cmd: {"command": cmd}),
        
        # read_file
        ("lee {file}", "read_file", lambda file: {"path": file}),
        ("muestra el contenido de {file}", "read_file", lambda file: {"path": file}),
        ("abre y lee {file}", "read_file", lambda file: {"path": file}),
        ("codigo de {file}", "read_file", lambda file: {"path": file}),
        
        # write_file
        ("escribe {content} en {file}", "write_file", lambda content, file: {"path": file, "content": content}),
        ("guarda {content} dentro de {file}", "write_file", lambda content, file: {"path": file, "content": content}),
        ("crea el archivo {file} con {content}", "write_file", lambda content, file: {"path": file, "content": content}),
        
        # search_files
        ("busca {pat} en el proyecto", "search_files", lambda pat: {"pattern": pat}),
        ("donde esta la palabra {pat} en el codigo", "search_files", lambda pat: {"pattern": pat}),
        ("encuentra coincidencias de {pat}", "search_files", lambda pat: {"pattern": pat}),
        
        # web_search
        ("busca en internet {q}", "web_search", lambda q: {"query": q}),
        ("investiga en la web sobre {q}", "web_search", lambda q: {"query": q}),
        ("que dice la web de {q}", "web_search", lambda q: {"query": q}),
        ("clima actual de {q} segun google", "web_search", lambda q: {"query": q}),
        
        # query_memory
        ("que sabes de {q} en mi memoria", "query_memory", lambda q: {"query": q}),
        ("busca en mi base de conocimiento {q}", "query_memory", lambda q: {"query": q}),
        ("recuerdas algo sobre {q}", "query_memory", lambda q: {"query": q}),
        
        # learn_fact
        ("aprende que {fact}", "learn_fact", lambda fact: {"fact": fact, "category": "general"}),
        ("guarda en memoria que {fact}", "learn_fact", lambda fact: {"fact": fact, "category": "general"}),
        ("recuerda el hecho {fact}", "learn_fact", lambda fact: {"fact": fact, "category": "general"}),
    ]

    # Datos para rellenar las plantillas
    commands = ["python main.py", "git status", "dir", "pip install requests", "pytest tests/"]
    files = ["config.py", "main.py", "index.html", "requirements.txt", "package.json"]
    contents = ["hola mundo", "api_key=12345", "test pass", "print('debug')"]
    patterns = ["def query_knowledge", "ContradictionError", "import sqlite3", "TODO"]
    queries = ["la fotosintesis", "barcelona fc", "el creador de python", "inteligencia artificial"]
    facts = ["mi cumpleaños es el 5 de mayo", "el servidor corre en el puerto 8000", "la clave secreta es nucleo"]

    # Generar iterativamente para lograr un volumen grande (> 80)
    for templ, tool, param_fn in templates:
        if tool == "run_command":
            for c in commands:
                user = templ.format(cmd=c)
                examples.append({
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user},
                        {"role": "assistant", "content": json.dumps({"accion": "usar_herramienta", "herramienta": tool, "parametros": param_fn(c)}, ensure_ascii=False)}
                    ]
                })
        elif tool == "read_file":
            for f in files:
                user = templ.format(file=f)
                examples.append({
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user},
                        {"role": "assistant", "content": json.dumps({"accion": "usar_herramienta", "herramienta": tool, "parametros": param_fn(f)}, ensure_ascii=False)}
                    ]
                })
        elif tool == "write_file":
            for ct in contents:
                for f in files[:3]:
                    user = templ.format(content=ct, file=f)
                    examples.append({
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user},
                            {"role": "assistant", "content": json.dumps({"accion": "usar_herramienta", "herramienta": tool, "parametros": param_fn(ct, f)}, ensure_ascii=False)}
                        ]
                    })
        elif tool == "search_files":
            for p in patterns:
                user = templ.format(pat=p)
                examples.append({
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user},
                        {"role": "assistant", "content": json.dumps({"accion": "usar_herramienta", "herramienta": tool, "parametros": param_fn(p)}, ensure_ascii=False)}
                    ]
                })
        elif tool == "web_search" or tool == "query_memory":
            for q in queries:
                user = templ.format(q=q)
                examples.append({
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user},
                        {"role": "assistant", "content": json.dumps({"accion": "usar_herramienta", "herramienta": tool, "parametros": param_fn(q)}, ensure_ascii=False)}
                    ]
                })
        elif tool == "learn_fact":
            for ft in facts:
                user = templ.format(fact=ft)
                examples.append({
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user},
                        {"role": "assistant", "content": json.dumps({"accion": "usar_herramienta", "herramienta": tool, "parametros": param_fn(ft)}, ensure_ascii=False)}
                    ]
                })

    # Guardar en archivo
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(examples, f, indent=2, ensure_ascii=False)

    print(f"Dataset generado exitosamente con {len(examples)} ejemplos en: {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_dataset()
