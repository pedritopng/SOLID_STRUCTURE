import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox
import os


def process_file(input_filename):
    """
    Reads the input file, automatically detecting if it's CSV or Excel.
    """
    # Check the file extension to decide how to read it
    _, file_extension = os.path.splitext(input_filename)

    if file_extension.lower() == '.csv':
        # Load as a CSV, skipping the first row, no header
        df = pd.read_csv(input_filename, header=None, skiprows=1)
    elif file_extension.lower() in ['.xlsx', '.xls']:
        # Load as an Excel file, skipping the first row, no header
        df = pd.read_excel(input_filename, header=None, skiprows=1)
    else:
        # If the file type is not supported, raise an error
        raise ValueError(f"Unsupported file type: {file_extension}")

    # Assign column names, assuming the structure is consistent
    df.columns = [
        'NIVEL', 'QTD', 'DESCRICAO', 'CODIGO', 'MATERIA_PRIMA',
        'DESC_MATERIA_PRIMA', 'MATERIAL', 'PESO'
    ]
    return df


def convert_to_parent_child_format(input_filename, output_filename, root_assembly_code='G12100400'):
    """
    Converts a hierarchical Bill of Materials (BOM) file to a parent-child relationship CSV.
    """
    try:
        # Use the new processing function to read the file
        df_structure = process_file(input_filename)

        parent_tracker = {-1: root_assembly_code}
        output_data = []

        for index, row in df_structure.iterrows():
            level_str = str(row['NIVEL'])
            child_code = row['CODIGO']
            quantity = row['QTD']
            depth = level_str.count('.')
            parent_code = parent_tracker[depth - 1]

            output_data.append({
                'EMPRESA': 1,
                'COD MTG': parent_code,
                'COD PEC': child_code,
                'QTD': quantity,
                'PERDA': 0
            })
            parent_tracker[depth] = child_code

        df_output = pd.DataFrame(output_data)
        df_output.to_csv(output_filename, sep=';', index=False)

        return True, f"Conversion successful!\nFile saved as:\n{output_filename}"

    except FileNotFoundError:
        return False, f"Error: The file '{input_filename}' was not found."
    except ValueError as ve:
        return False, str(ve)
    except KeyError as e:
        return False, f"Error: A hierarchy level was likely skipped or a column is missing. Details: {e}"
    except Exception as e:
        return False, f"An unexpected error occurred: {e}"


# --- GUI Application ---
class BomConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BOM Converter")
        self.root.geometry("400x250")

        frame = tk.Frame(root, padx=10, pady=10)
        frame.pack(expand=True)

        tk.Label(frame, text="Root Assembly Code:").grid(row=0, column=0, sticky="w", pady=5)
        self.root_code_entry = tk.Entry(frame, width=30)
        self.root_code_entry.insert(0, "G12100400")
        self.root_code_entry.grid(row=0, column=1, pady=5)

        self.convert_button = tk.Button(frame, text="Select File and Convert", command=self.run_conversion, height=2,
                                        width=30)
        self.convert_button.grid(row=1, column=0, columnspan=2, pady=20)

        self.status_label = tk.Label(frame, text="Please select an Excel or CSV file to convert.", wraplength=380)
        self.status_label.grid(row=2, column=0, columnspan=2, pady=10)

    def run_conversion(self):
        input_file = filedialog.askopenfilename(
            title="Select the Hierarchical BOM File",
            # **UPDATED:** Now includes Excel files and makes them the default
            filetypes=(
                ("Excel files", "*.xlsx *.xls"),
                ("CSV files", "*.csv"),
                ("All files", "*.*")
            )
        )

        if not input_file:
            self.status_label.config(text="Operation cancelled. No file selected.")
            return

        root_code = self.root_code_entry.get()
        if not root_code:
            messagebox.showerror("Error", "Root Assembly Code cannot be empty.")
            return

        directory, filename = os.path.split(input_file)
        name, _ = os.path.splitext(filename)
        output_file = os.path.join(directory, f"{name}_converted.csv")

        success, message = convert_to_parent_child_format(input_file, output_file, root_code)

        if success:
            messagebox.showinfo("Success", message)
            self.status_label.config(text="Ready for next conversion.")
        else:
            messagebox.showerror("Error", message)
            self.status_label.config(text="An error occurred during conversion.")


# --- SCRIPT EXECUTION ---
if __name__ == "__main__":
    # You need to install the 'openpyxl' library for pandas to read .xlsx files
    # Run this command in your terminal: pip install openpyxl
    root = tk.Tk()
    app = BomConverterApp(root)
    root.mainloop()

