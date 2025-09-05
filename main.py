import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox
import os


def convert_to_parent_child_format(input_filename, output_filename, root_assembly_code='G12100400'):
    """
    Converts a hierarchical Bill of Materials (BOM) CSV to a parent-child relationship CSV.
    This version is designed to be called from a GUI.
    """
    try:
        # Load the CSV by skipping the first blank row and without treating
        # any specific row as the header. This ensures all data is read.
        df_structure = pd.read_csv(input_filename, header=None, skiprows=1)

        # Assign clear, consistent column names manually for easy access.
        df_structure.columns = [
            'NIVEL', 'QTD', 'DESCRICAO', 'CODIGO', 'MATERIA_PRIMA',
            'DESC_MATERIA_PRIMA', 'MATERIAL', 'PESO'
        ]

        # This dictionary tracks the current parent code at each hierarchy level.
        parent_tracker = {-1: root_assembly_code}
        output_data = []

        # Iterate through each component in the input structure file.
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
    except KeyError as e:
        return False, f"Error: A hierarchy level was likely skipped in the input file, leading to a missing parent. Details: {e}"
    except Exception as e:
        return False, f"An unexpected error occurred: {e}"


# --- GUI Application ---
class BomConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BOM Converter")
        self.root.geometry("400x250")

        # Frame for widgets
        frame = tk.Frame(root, padx=10, pady=10)
        frame.pack(expand=True)

        # Root Assembly Code Input
        tk.Label(frame, text="Root Assembly Code:").grid(row=0, column=0, sticky="w", pady=5)
        self.root_code_entry = tk.Entry(frame, width=30)
        self.root_code_entry.insert(0, "G12100400")
        self.root_code_entry.grid(row=0, column=1, pady=5)

        # Main Button
        self.convert_button = tk.Button(frame, text="Select File and Convert", command=self.run_conversion, height=2,
                                        width=30)
        self.convert_button.grid(row=1, column=0, columnspan=2, pady=20)

        # Status Label
        self.status_label = tk.Label(frame, text="Please select a file to convert.", wraplength=380)
        self.status_label.grid(row=2, column=0, columnspan=2, pady=10)

    def run_conversion(self):
        input_file = filedialog.askopenfilename(
            title="Select the Hierarchical BOM CSV File",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*"))
        )

        if not input_file:
            self.status_label.config(text="Operation cancelled. No file selected.")
            return

        root_code = self.root_code_entry.get()
        if not root_code:
            messagebox.showerror("Error", "Root Assembly Code cannot be empty.")
            return

        # Propose an output filename
        directory, filename = os.path.split(input_file)
        name, ext = os.path.splitext(filename)
        output_file = os.path.join(directory, f"{name}_converted.csv")

        # Run the conversion logic
        success, message = convert_to_parent_child_format(input_file, output_file, root_code)

        if success:
            messagebox.showinfo("Success", message)
            self.status_label.config(text="Ready for next conversion.")
        else:
            messagebox.showerror("Error", message)
            self.status_label.config(text="An error occurred.")


# --- SCRIPT EXECUTION ---
if __name__ == "__main__":
    root = tk.Tk()
    app = BomConverterApp(root)
    root.mainloop()

