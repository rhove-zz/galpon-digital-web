#!/usr/bin/env python3
"""
ACU Quick Setup Script
Automatiza la configuración inicial del proyecto
"""
import os
import sys
import subprocess
from pathlib import Path


def print_banner():
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║   ACU QUICK SETUP - Agente Cognitivo Universal v1.0        ║
    ║                                                              ║
    ║   Setup automático del entorno                              ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)


def check_python_version():
    """Verificar versión de Python."""
    print("\n✓ Verificando Python...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print(f"✗ Se requiere Python 3.11+, tienes {version.major}.{version.minor}")
        return False
    print(f"✓ Python {version.major}.{version.minor} OK")
    return True


def create_venv():
    """Crear ambiente virtual."""
    print("\n✓ Creando ambiente virtual...")
    venv_path = Path("venv")
    
    if venv_path.exists():
        print("  (Ya existe, saltando)")
        return True
    
    try:
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print("✓ Ambiente virtual creado")
        return True
    except subprocess.CalledProcessError:
        print("✗ Error creando venv")
        return False


def activate_venv():
    """Get activation command for venv."""
    if os.name == 'nt':
        return r"venv\Scripts\activate"
    return "source venv/bin/activate"


def install_requirements():
    """Instalar dependencias."""
    print("\n✓ Instalando dependencias...")
    
    pip_cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-r",
        "requirements.txt"
    ]
    
    try:
        subprocess.run(pip_cmd, check=True)
        print("✓ Dependencias instaladas")
        return True
    except subprocess.CalledProcessError:
        print("✗ Error instalando dependencias")
        return False


def setup_env():
    """Configurar .env."""
    print("\n✓ Configurando .env...")
    
    env_path = Path(".env")
    example_path = Path(".env.example")
    
    if env_path.exists():
        print("  (Ya existe .env, saltando)")
        return True
    
    if not example_path.exists():
        print("✗ No se encontró .env.example")
        return False
    
    # Copiar template
    with open(example_path) as f:
        content = f.read()
    
    with open(env_path, "w") as f:
        f.write(content)
    
    print("✓ .env creado (editar con tus valores)")
    return True


def check_ollama():
    """Verificar si Ollama está disponible."""
    print("\n✓ Verificando Ollama...")
    
    try:
        response = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/tags"],
            capture_output=True,
            timeout=2
        )
        if response.returncode == 0:
            print("✓ Ollama está corriendo")
            return True
    except Exception:
        pass
    
    print("⚠ Ollama no está disponible")
    print("  Instala Ollama: https://ollama.ai")
    print("  Luego ejecuta: ollama serve")
    return False


def create_logs_dir():
    """Crear directorio de logs."""
    print("\n✓ Creando directorios...")
    
    logs_dir = Path("logs")
    data_dir = Path("data") / "vectors"
    
    logs_dir.mkdir(exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"✓ Directorios creados")
    return True


def print_next_steps():
    """Mostrar próximos pasos."""
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                    PRÓXIMOS PASOS                            ║
    ╚══════════════════════════════════════════════════════════════╝
    
    1. CONFIGURAR VARIABLES
       - Edita .env con:
         • MYSQL_HOST, MYSQL_PASSWORD
         • OLLAMA_HOST, OLLAMA_MODEL
    
    2. DESCARGAR MODELO OLLAMA (en otra terminal)
       $ ollama pull mistral
       (o: gemma, neural-chat, etc)
    
    3. VERIFICAR MYSQL (o usar Docker)
       $ docker run -d -p 3306:3306 -e MYSQL_ROOT_PASSWORD=root mysql:8.0
       
    4. EJECUTAR EL AGENTE
       $ python main.py
    
    5. O USAR DOCKER COMPOSE (recomendado)
       $ cd docker
       $ docker-compose up -d
    
    ═══════════════════════════════════════════════════════════════
    
    📚 DOCUMENTACIÓN:
       - README.md         → Guía general
       - ARCHITECTURE.md   → Detalles técnicos
       - USAGE.md          → Ejemplos de uso
    
    💬 PRIMERA EJECUCIÓN:
       $ python main.py
       👤 Tú: ¿Cuántos usuarios activos hay?
       🤖 Agente: [ejecuta herramientas y responde]
    
    ═══════════════════════════════════════════════════════════════
    """)


def main():
    print_banner()
    
    steps = [
        ("Versión Python", check_python_version),
        ("Ambiente Virtual", create_venv),
        ("Dependencias", install_requirements),
        ("Configuración .env", setup_env),
        ("Directorios", create_logs_dir),
        ("Ollama", check_ollama),
    ]
    
    failed = []
    
    for name, func in steps:
        try:
            if not func():
                failed.append(name)
        except Exception as e:
            print(f"✗ Error en {name}: {e}")
            failed.append(name)
    
    print("\n" + "="*60)
    
    if failed:
        print(f"⚠ Se encontraron {len(failed)} problemas:")
        for item in failed:
            print(f"  - {item}")
        print("\n📌 Revisa los mensajes anteriores y resuelve antes de continuar")
    else:
        print("✅ SETUP COMPLETADO EXITOSAMENTE")
        print_next_steps()
    
    print("="*60)
    
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
