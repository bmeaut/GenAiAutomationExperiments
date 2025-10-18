"""
Excel Makró Injektáló - Neptun Anonimizáló
Végigpásztázza a könyvtárat Excel fájlok után és hozzáadja a NeptunAnonymizer makrót minden fájlhoz.
Elmenti a fájlokat .xlsm (makró-kompatibilis) formátumban egy kimeneti könyvtárba.
"""

import os
import argparse
from pathlib import Path
import win32com.client
import tkinter as tk
from tkinter import filedialog

def select_folder(title, initial_dir=None):
    """Mappa kiválasztó ablak megjelenítése"""
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    root.attributes('-topmost', True)  # Bring dialog to front
    
    folder_path = filedialog.askdirectory(
        title=title,
        initialdir=initial_dir
    )
    
    root.destroy()
    return folder_path

def select_file(title, initial_dir=None, filetypes=None):
    """Fájl kiválasztó ablak megjelenítése"""
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    
    if filetypes is None:
        filetypes = [("VBA Fájlok", "*.bas"), ("Minden fájl", "*.*")]
    
    file_path = filedialog.askopenfilename(
        title=title,
        initialdir=initial_dir,
        filetypes=filetypes
    )
    
    root.destroy()
    return file_path

def read_vba_code(vba_file_path):
    """VBA kód beolvasása .bas fájlból"""
    try:
        with open(vba_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        # Try with different encoding if UTF-8 fails
        with open(vba_file_path, 'r', encoding='latin-1') as f:
            content = f.read()
    
    # Remove VBA export attributes (Attribute lines)
    # These cause syntax errors when added via AddFromString
    # VBA export attribútumok eltávolítása (Attribute sorok)
    # Ezek szintaxis hibát okoznak az AddFromString használatakor
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        # Skip lines starting with "Attribute" (case-insensitive)
        # Az "Attribute"-tal kezdődő sorok kihagyása
        if not line.strip().upper().startswith('ATTRIBUTE '):
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)

def add_macro_to_workbook(excel_app, workbook_path, vba_code, output_path):
    """VBA makró hozzáadása Excel munkafüzethez"""
    try:
        # Open workbook
        wb = excel_app.Workbooks.Open(workbook_path)
        
        # Access VBA project
        vb_project = wb.VBProject
        
        # Check if module already exists
        module_name = "NeptunAnonymizer"
        module_exists = False
        
        for component in vb_project.VBComponents:
            if component.Name == module_name:
                print(f"  - A(z) '{module_name}' modul már létezik, régi verzió eltávolítása...")
                vb_project.VBComponents.Remove(component)
                break
        
        # Add new module
        vb_module = vb_project.VBComponents.Add(1)  # 1 = vbext_ct_StdModule
        vb_module.Name = module_name
        
        # Add code to module
        vb_module.CodeModule.AddFromString(vba_code)
        
        # Save as macro-enabled workbook (.xlsm)
        wb.SaveAs(output_path, FileFormat=52)  # 52 = xlOpenXMLWorkbookMacroEnabled
        wb.Close(SaveChanges=True)
        
        return True
    except Exception as e:
        err = str(e)
        # Detect known VBA project access error and print Hungarian instructions
        if ("Nincs jogosultság" in err) or ("not trusted" in err):
            print("\nFIGYELEM: A makró hozzáadása sikertelen, mert nincs programozási hozzáférés a VBA projekthez.")
            print("Engedélyezze az Excel beállításaiban a hozzáférést a következőképpen:")
            print("  1) Nyissa meg az Excel-t.")
            print("  2) Fájl -> Beállítások (File -> Options).")
            print("  3) Adatvédelmi központ -> Az Adatvédelmi központ beállításai... (Trust Center -> Trust Center Settings...).")
            print("  4) Makróbeállítások (Macro Settings) fülön jelölje be: ")
            print("      'A VBA-projekt objektummodelljéhez való hozzáférés megbízható' (Trust access to the VBA project object model).")
            print("  5) OK, majd zárja be az Excel-t.")
            print("Ezután futtassa újra a szkriptet.\n")
        else:
            print(f"  HIBA: {err}")
        try:
            wb.Close(SaveChanges=False)
        except:
            pass
        return False

def process_directory(input_dir, output_dir, vba_file_path):
    """Minden Excel fájl feldolgozása a bemeneti könyvtárban"""
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Read VBA code
    print(f"VBA kód beolvasása: {vba_file_path}")
    vba_code = read_vba_code(vba_file_path)
    print(f"VBA kód sikeresen betöltve ({len(vba_code)} karakter)\n")
    
    # Try to connect to existing Excel instance
    excel_app = None
    excel_was_running = False
    try:
        excel_app = win32com.client.GetActiveObject("Excel.Application")
        excel_was_running = True
        print("Csatlakozás a meglévő Excel példányhoz...")
    except:
        # No existing instance, create new one
        excel_app = win32com.client.Dispatch("Excel.Application")
        excel_app.Visible = False
        print("Excel indítása...")
    
    # If we started Excel, hide it and disable alerts
    if not excel_was_running:
        excel_app.Visible = False
    
    excel_app.DisplayAlerts = False
    
    # Enable VBA project access (must be enabled in Excel Trust Center)
    try:
        excel_app.VBE.MainWindow.Visible = False
    except:
        print("FIGYELMEZTETÉS: A VBA projekt hozzáférés korlátozva lehet.")
        print("Kérjük, engedélyezze a 'A VBA-projekt objektummodelljéhez való hozzáférés megbízható' opciót az Excel Adatvédelmi központjában.\n")
    
    # Supported Excel extensions
    excel_extensions = ['.xlsx', '.xls', '.xlsm', '.xlsb']
    
    # Normalize paths for comparison
    input_path = Path(input_dir).resolve()
    output_path = Path(output_dir).resolve()
    
    # Find all Excel files, excluding the output directory
    excel_files = []
    for ext in excel_extensions:
        for file in input_path.glob(f'**/*{ext}'):
            # Skip files in the output directory
            try:
                if not file.resolve().is_relative_to(output_path):
                    excel_files.append(file)
            except (ValueError, AttributeError):
                # For Python < 3.9, use alternative method
                try:
                    file.resolve().relative_to(output_path)
                    # If no error, file is in output dir, skip it
                except ValueError:
                    # File is not in output dir, include it
                    excel_files.append(file)
    
    if not excel_files:
        print(f"Nem található Excel fájl itt: {input_dir}")
        excel_app.Quit()
        return
    
    print(f"{len(excel_files)} Excel fájl található feldolgozásra:\n")
    
    # Process each file
    success_count = 0
    failed_count = 0
    
    for excel_file in excel_files:
        rel_path = excel_file.relative_to(input_path)
        output_file = output_path / rel_path.with_suffix('.xlsm')
        
        # Create subdirectories in output if needed
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"Feldolgozás: {rel_path}")
        print(f"  Kimenet: {output_file.name}")
        
        if add_macro_to_workbook(excel_app, str(excel_file.absolute()), vba_code, str(output_file.absolute())):
            print(f"  ✓ SIKERES\n")
            success_count += 1
        else:
            print(f"  ✗ SIKERTELEN\n")
            failed_count += 1
    
    # Cleanup
    # Only quit Excel if we started it
    if not excel_was_running:
        excel_app.Quit()
    else:
        excel_app.DisplayAlerts = True
    
    # Summary
    print("=" * 60)
    print(f"Feldolgozás befejezve!")
    print(f"  Sikeres: {success_count}")
    print(f"  Sikertelen: {failed_count}")
    print(f"  Kimeneti könyvtár: {output_dir}")
    print("=" * 60)

def main():
    """Fő belépési pont"""
    
    # Get script directory
    script_dir = Path(__file__).parent
    
    # Default VBA file path
    default_vba = script_dir / "NeptunAnonymizer.bas"
    
    # Setup argument parser
    parser = argparse.ArgumentParser(
        description='Excel Makró Injektáló - Hozzáad egy makrót Excel fájlokhoz',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=''':
Példák:
  %(prog)s . output                                      # Aktuális könyvtár feldolgozása
  %(prog)s . output NeptunAnonymizer.bas                 # VBA fájl megadása
  %(prog)s input output                                  # 'input' mappa feldolgozása
  %(prog)s                                               # GUI mappakiválasztó használata
        '''
    )
    
    parser.add_argument(
        'input_dir',
        nargs='?',
        help='Bemeneti könyvtár Excel fájlokkal (.xlsx, .xls, .xlsm, .xlsb)'
    )
    
    parser.add_argument(
        'output_dir',
        nargs='?',
        help='Kimeneti könyvtár a feldolgozott .xlsm fájloknak'
    )
    
    parser.add_argument(
        'vba_file',
        nargs='?',
        default=str(default_vba) if default_vba.exists() else None,
        help=f'VBA makró fájl elérési útja (.bas) (alapértelmezett: {default_vba.name})'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 1.0'
    )
    
    args = parser.parse_args()
    
    # Get input directory from args or folder picker
    if args.input_dir:
        input_dir = args.input_dir
    else:
        print("Válassza ki az Excel fájlokat tartalmazó bemeneti könyvtárat...")
        input_dir = select_folder(
            "Válasszon Bemeneti Könyvtárat (Excel fájlok)",
            initial_dir=str(script_dir)
        )
        if not input_dir:
            print("HIBA: Nincs kiválasztva bemeneti könyvtár. Kilépés.")
            return
    
    # Get output directory from args or folder picker
    if args.output_dir:
        output_dir = args.output_dir
    else:
        print("Válassza ki a feldolgozott fájlok kimeneti könyvtárát...")
        output_dir = select_folder(
            "Válasszon Kimeneti Könyvtárat (.xlsm fájlokhoz)",
            initial_dir=str(script_dir)
        )
        if not output_dir:
            print("HIBA: Nincs kiválasztva kimeneti könyvtár. Kilépés.")
            return
    
    # Get VBA file from args or file picker
    if args.vba_file:
        vba_file = args.vba_file
    else:
        print("Válassza ki a VBA makró fájlt...")
        vba_file = select_file(
            "Válasszon VBA Makró Fájlt (.bas)",
            initial_dir=str(script_dir),
            filetypes=[("VBA Fájlok", "*.bas"), ("Minden fájl", "*.*")]
        )
        if not vba_file:
            print("HIBA: Nincs kiválasztva VBA fájl. Kilépés.")
            return
    
    # Validate paths
    if not os.path.exists(input_dir):
        print(f"HIBA: Bemeneti könyvtár nem található: {input_dir}")
        return
    
    if not os.path.exists(vba_file):
        print(f"HIBA: VBA fájl nem található: {vba_file}")
        return
    
    print("\n" + "=" * 60)
    print("Excel Makró Injektáló")
    print("=" * 60)
    print(f"Bemeneti könyvtár:  {input_dir}")
    print(f"Kimeneti könyvtár:  {output_dir}")
    print(f"VBA makró fájl:     {vba_file}")
    print("=" * 60 + "\n")
    
    # Process files
    process_directory(input_dir, output_dir, vba_file)

if __name__ == "__main__":
    main()
