"""
Nucleo Nexus — Ejecutor Unificado de Pruebas Unitarias
======================================================
Busca y ejecuta todos los archivos test_*.py en tests/ y muestra resultados estructurados.
"""
import unittest
import sys
import os
from pathlib import Path

# Cargar path del proyecto
BASE = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(BASE))

# Silenciar logs molestos del logger
os.environ["LOG_LEVEL"] = "ERROR"

def run_suite():
    print("=" * 70)
    print(" EJECUTANDO SUITE DE PRUEBAS MODULARES - NUCLEONEXUS")
    print("=" * 70)
    
    # Crear cargador de test
    loader = unittest.TestLoader()
    
    # Buscar archivos test_*.py en el directorio tests/
    # Ignorar test_regression.py para evitar correr duplicados
    tests_dir = str(Path(__file__).parent)
    suite = unittest.TestSuite()
    
    for root, dirs, files in os.walk(tests_dir):
        for file in files:
            if file.startswith("test_") and file.endswith(".py") and file != "test_regression.py":
                module_name = f"tests.{file[:-3]}"
                try:
                    loaded_tests = loader.loadTestsFromName(module_name)
                    suite.addTests(loaded_tests)
                except Exception as e:
                    print(f"Error cargando tests de {file}: {e}")

    # Ejecutar suite
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 70)
    print(" RESUMEN DE PRUEBAS")
    print("=" * 70)
    print(f"  Total Ejecutadas: {result.testsRun}")
    print(f"  Exitosas:         {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  Fallidas:         {len(result.failures)}")
    print(f"  Errores:          {len(result.errors)}")
    
    if not result.wasSuccessful():
        print("\n DETALLE DE ERRORES/FALLOS:")
        for failure in result.failures:
            print(f"  - FALLO en {failure[0]}:")
            print(failure[1])
        for error in result.errors:
            print(f"  - ERROR en {error[0]}:")
            print(error[1])
        sys.exit(1)
        
    print("\n✓ ¡Todas las pruebas modularizadas pasaron con éxito!")
    print("=" * 70)
    sys.exit(0)

if __name__ == "__main__":
    run_suite()
