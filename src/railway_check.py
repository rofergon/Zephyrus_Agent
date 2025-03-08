#!/usr/bin/env python
"""
Script de diagnóstico para Railway. Este script imprime información sobre el entorno
y las variables de configuración para ayudar a diagnosticar problemas de despliegue.
"""

import os
import sys
import socket
import platform
import json

# Añadir el directorio raíz al PYTHONPATH para poder importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.utils.config import WS_HOST, WS_PORT
    from src.utils.logger import setup_logger
    
    logger = setup_logger("railway_check")
    
    # Función para imprimir información de diagnóstico
    def print_diagnostic_info():
        print("\n==== RAILWAY DIAGNOSTIC INFO ====\n")
        
        # Información del sistema
        print(f"Python version: {sys.version}")
        print(f"Platform: {platform.platform()}")
        print(f"System: {platform.system()} {platform.release()}")
        
        # Variables de entorno relevantes
        print("\n-- Environment Variables --")
        env_vars = {
            "PORT": os.environ.get("PORT", "Not set"),
            "WS_PORT": os.environ.get("WS_PORT", "Not set"),
            "WS_HOST": os.environ.get("WS_HOST", "Not set"),
            "RAILWAY_STATIC_URL": os.environ.get("RAILWAY_STATIC_URL", "Not set"),
            "RAILWAY_PUBLIC_DOMAIN": os.environ.get("RAILWAY_PUBLIC_DOMAIN", "Not set"),
            "RAILWAY_GIT_COMMIT_SHA": os.environ.get("RAILWAY_GIT_COMMIT_SHA", "Not set"),
            "PATH": os.environ.get("PATH", "Not set")
        }
        
        for key, value in env_vars.items():
            print(f"{key}: {value}")
        
        # Configuración cargada
        print("\n-- Loaded Configuration --")
        print(f"WS_HOST from config.py: {WS_HOST}")
        print(f"WS_PORT from config.py: {WS_PORT}")
        
        # Verificar puertos disponibles
        print("\n-- Port Check --")
        test_port = int(os.environ.get("PORT", WS_PORT))
        print(f"Testing port {test_port}...")
        
        try:
            # Comprobar si el puerto ya está en uso
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex(('localhost', test_port))
            if result == 0:
                print(f"Port {test_port} is already in use!")
            else:
                print(f"Port {test_port} is available")
            s.close()
            
            # Intentar enlazar a 0.0.0.0 con el puerto de Railway
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.bind(('0.0.0.0', test_port))
            print(f"Successfully bound to 0.0.0.0:{test_port}")
            s.close()
        except Exception as e:
            print(f"Error testing port: {str(e)}")
        
        print("\n-- Network Interfaces --")
        import netifaces
        for interface in netifaces.interfaces():
            print(f"\nInterface: {interface}")
            try:
                addresses = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addresses:
                    for address in addresses[netifaces.AF_INET]:
                        print(f"  IPv4: {address.get('addr')} Netmask: {address.get('netmask')}")
                if netifaces.AF_INET6 in addresses:
                    for address in addresses[netifaces.AF_INET6]:
                        print(f"  IPv6: {address.get('addr')} Scope: {address.get('scope')}")
            except Exception as e:
                print(f"  Error reading interface information: {str(e)}")
                
        print("\n==== END DIAGNOSTIC INFO ====\n")
        
    # Ejecutar el diagnóstico
    if __name__ == "__main__":
        try:
            print_diagnostic_info()
        except Exception as e:
            print(f"Error during diagnostic: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
except Exception as e:
    print(f"Failed to import modules: {str(e)}")
    import traceback
    traceback.print_exc() 