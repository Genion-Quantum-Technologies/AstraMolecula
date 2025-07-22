#!/usr/bin/env python3
"""
Script to fix PDBQT file formatting issues
"""

def fix_pdbqt_format(input_file, output_file):
    """
    Fix PDBQT file formatting by ensuring proper line endings and formatting
    """
    with open(input_file, 'r') as f:
        lines = f.readlines()
    
    fixed_lines = []
    for line in lines:
        # Remove trailing spaces and ensure proper line ending
        line = line.rstrip() + '\n'
        
        # Skip empty lines
        if not line.strip():
            continue
            
        # Process ATOM lines
        if line.startswith('ATOM') or line.startswith('HETATM'):
            # Ensure proper PDBQT format
            # ATOM lines should have exactly the right number of fields
            parts = line.split()
            if len(parts) >= 11:
                # Reconstruct the line with proper formatting
                # Format: ATOM serial name resName chainID resSeq x y z occupancy tempFactor charge atomType
                try:
                    serial = parts[1]
                    name = parts[2]
                    resName = parts[3]
                    chainID = parts[4]
                    resSeq = parts[5]
                    x = float(parts[6])
                    y = float(parts[7]) 
                    z = float(parts[8])
                    occupancy = float(parts[9])
                    tempFactor = float(parts[10])
                    
                    # Check if charge and atom type are present
                    if len(parts) >= 12:
                        charge = float(parts[11])
                    else:
                        charge = 0.0
                        
                    if len(parts) >= 13:
                        atomType = parts[12]
                    else:
                        # Infer atom type from atom name
                        atomType = parts[2][0]  # First character of atom name
                    
                    # Reconstruct line with proper PDBQT formatting
                    fixed_line = f"ATOM  {serial:>5s} {name:>4s} {resName:>3s} {chainID:>1s}{resSeq:>4s}    {x:8.3f}{y:8.3f}{z:8.3f}{occupancy:6.2f}{tempFactor:6.2f}    {charge:6.3f} {atomType:<2s}\n"
                    fixed_lines.append(fixed_line)
                except (ValueError, IndexError) as e:
                    print(f"Error processing line: {line.strip()}")
                    print(f"Error: {e}")
                    # Keep original line if parsing fails
                    fixed_lines.append(line)
            else:
                # Keep original line if not enough parts
                fixed_lines.append(line)
        else:
            # Keep non-ATOM lines as is
            fixed_lines.append(line)
    
    # Write fixed file
    with open(output_file, 'w') as f:
        f.writelines(fixed_lines)
    
    print(f"Fixed PDBQT file written to: {output_file}")

if __name__ == "__main__":
    import sys
    
    input_file = "/Users/youngwild/Dev/jingyuan/dockingVina/resource/protein_7UDP.pdbqt"
    output_file = "/Users/youngwild/Dev/jingyuan/dockingVina/resource/protein_7UDP_fixed.pdbqt"
    
    print(f"Fixing PDBQT file: {input_file}")
    fix_pdbqt_format(input_file, output_file)
    
    # Show first few lines of fixed file
    print("\nFirst 10 lines of fixed file:")
    with open(output_file, 'r') as f:
        for i, line in enumerate(f):
            if i < 10:
                print(f"{i+1:2d}: {line.rstrip()}")
            else:
                break
