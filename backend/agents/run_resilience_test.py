import unittest
import sys
import os

# Adicionar o diretório atual ao path para importar os agentes
sys.path.append(os.getcwd())

from agents.test_database_resilience import TestStateManagerIsolation, TestBaseSpecialistPattern

if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestStateManagerIsolation)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestBaseSpecialistPattern))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("\n✅ Todos os testes de resiliência passaram!")
        sys.exit(0)
    else:
        print("\n❌ Alguns testes falharam.")
        sys.exit(1)
