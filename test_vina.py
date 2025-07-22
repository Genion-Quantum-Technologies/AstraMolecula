#!/usr/bin/env python3
"""
Test script to check Vina installation and API
"""

def test_vina_installation():
    """Test Vina installation and basic functionality"""
    try:
        from vina import Vina
        print("✅ Vina imported successfully")
        
        # Test creating Vina object
        v = Vina(sf_name='vina')
        print("✅ Vina object created successfully")
        
        # Check Vina version and methods
        print(f"Vina object type: {type(v)}")
        print("Available methods:")
        methods = [method for method in dir(v) if not method.startswith('_')]
        for method in sorted(methods):
            print(f"  - {method}")
        
        # Test receptor setting methods
        receptor_file = "/Users/youngwild/Dev/jingyuan/dockingVina/resource/protein_7UDP.pdbqt"
        print(f"\nTesting receptor file: {receptor_file}")
        
        import os
        if os.path.exists(receptor_file):
            print("✅ Receptor file exists")
            
            # Check file size and first few lines
            file_size = os.path.getsize(receptor_file)
            print(f"File size: {file_size} bytes")
            
            with open(receptor_file, 'r') as f:
                first_lines = [f.readline().strip() for _ in range(3)]
                print(f"First 3 lines: {first_lines}")
            
            # Test different receptor setting methods
            print("\nTesting receptor setting methods:")
            
            # Method 1: Direct string path
            try:
                v1 = Vina(sf_name='vina')
                v1.set_receptor(receptor_file)
                print("✅ Method 1 (string path) works")
                v1 = None  # Clean up
            except Exception as e:
                print(f"❌ Method 1 failed: {e}")
            
            # Method 2: With rigid parameter name
            try:
                v2 = Vina(sf_name='vina')
                v2.set_receptor(rigid_pdbqt_filename=receptor_file)
                print("✅ Method 2 (rigid_pdbqt_filename) works")
                v2 = None  # Clean up
            except Exception as e:
                print(f"❌ Method 2 failed: {e}")
            
            # Method 3: Read file content
            try:
                v3 = Vina(sf_name='vina')
                with open(receptor_file, 'r') as f:
                    content = f.read()
                v3.set_receptor(content)
                print("✅ Method 3 (file content) works")
                v3 = None  # Clean up
            except Exception as e:
                print(f"❌ Method 3 failed: {e}")
                
        else:
            print("❌ Receptor file does not exist")
            
    except ImportError as e:
        print(f"❌ Failed to import Vina: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    test_vina_installation()
