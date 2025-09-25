"""
Interface gráfica para o sistema SOLID_STRUCTURE.
Implementa o princípio Single Responsibility Principle (SRP) e Dependency Inversion Principle (DIP).
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import os
import sys
from typing import Optional

from ..core.models import ConversionRequest
from ..core.validators import AssemblyCodeValidator
from ..core.converter import xlsx_to_parent_child_csv, MultiTypeConverter
from ..core.conversion_types import ConversionType, get_conversion_types_for_gui


class SOLIDStructureGUI:
    """
    Classe principal da interface gráfica.
    Responsável apenas pela apresentação e interação com o usuário.
    """
    
    def __init__(self, root):
        self.root = root
        self.root.title("SOLID_STRUCTURE")
        self.root.geometry("700x900")
        self.root.resizable(False, False)
        
        # Initialize validators and converters
        self.assembly_validator = AssemblyCodeValidator()
        self.multi_converter = MultiTypeConverter()
        
        # Initialize conversion type selection
        self.selected_conversion_type = ConversionType.HIERARCHICAL_STRUCTURE
        self.conversion_type_selected_by_user = False
        
        # Dark theme color scheme
        self.colors = {
            'primary': '#C40024',      # Darker red from the cube
            'secondary': '#3498DB',    # Bright blue from neo CORP sticker
            'accent': '#FF4500',       # Orange-red highlight from cube
            'success': '#E4002B',      # Red for success (brand consistency)
            'warning': '#FF4500',      # Orange-red for warnings
            'danger': '#FF6B6B',       # Lighter red for errors in dark theme
            'light': '#1A1A1A',        # Dark background
            'dark': '#E8EAED',         # Light text for dark theme
            'white': '#2D2D2D',        # Dark card background
            'gray_100': '#3A3A3A',     # Dark gray for cards
            'gray_200': '#4A4A4A',     # Dark gray borders
            'gray_300': '#5A5A5A',     # Medium dark gray
            'gray_400': '#7A7A7A',     # Medium gray
            'gray_500': '#9A9A9A',     # Light gray
            'gray_600': '#BABABA',     # Lighter gray
            'gray_700': '#DADADA',     # Very light gray
            'gray_800': '#E8EAED',     # Almost white
            'gray_900': '#FFFFFF'      # White
        }
        
        self.root.configure(bg=self.colors['light'])
        
        # Configure dark theme for ttk widgets
        self.style = ttk.Style()
        self.style.configure("DarkEntry.TEntry",
                            fieldbackground=self.colors['gray_200'],
                            foreground="black",
                            insertcolor="black",
                            borderwidth=1,
                            relief="solid")
        
        # Configure progress bar style
        self.style.configure("Dark.Horizontal.TProgressbar",
                            background=self.colors['primary'],
                            troughcolor=self.colors['gray_300'],
                            borderwidth=1,
                            lightcolor=self.colors['primary'],
                            darkcolor=self.colors['primary'])
        
        # Set window icon
        self._set_window_icon()
        
        # State management variables
        self.selected_input_file = None
        self.last_generated_file = None
        self.last_input_file_hash = None
        self.last_assembly_code = None
        self.conversion_completed = False
        self.current_output_file = None
        self.assembly_code_valid = False
        self.conversion_in_progress = False
        self.dev_mode_active = False
        
        # Load brand logo
        self.logo_image = None
        self._load_brand_logo()
        
        # Create UI components
        self._create_ui()
        
        # Start periodic file checking
        # Removed periodic file check - now using event-based triggers only

        # Developer mode: auto-select example file and default assembly code for faster testing
        self._apply_dev_defaults()
    
    def _set_window_icon(self):
        """Set the window icon."""
        try:
            icon_path = "SOLID_STRUCTURE.ico"
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
            else:
                # Try alternative path for when running from different directory
                alt_icon_path = os.path.join(os.path.dirname(__file__), "..", "..", "SOLID_STRUCTURE.ico")
                if os.path.exists(alt_icon_path):
                    self.root.iconbitmap(alt_icon_path)
        except Exception as e:
            # If icon loading fails, continue without it
            print(f"Warning: Could not load icon: {e}")
    
    def _load_brand_logo(self):
        """Load the brand logo from PNG file."""
        try:
            logo_path = "SOLID_STRUCTURE.png"
            if not os.path.exists(logo_path):
                logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "SOLID_STRUCTURE.png")
            
            if os.path.exists(logo_path):
                # Load and resize the logo
                image = Image.open(logo_path)
                # Resize to appropriate size for the header
                image = image.resize((80, 80), Image.Resampling.LANCZOS)
                self.logo_image = ImageTk.PhotoImage(image)
            else:
                print("Warning: SOLID_STRUCTURE.png not found")
        except Exception as e:
            print(f"Warning: Could not load logo: {e}")

    def _apply_dev_defaults(self):
        """When SOLID_DEV=1, prefill sample file and assembly code for faster testing."""
        try:
            if os.environ.get('SOLID_DEV', '0') != '1':
                return
            # Locate example file in project root
            candidate = os.path.join(os.path.dirname(__file__), "..", "..", "EXEMPLO LISTA DE MONTAGEM.xlsx")
            candidate = os.path.abspath(candidate)
            if os.path.exists(candidate):
                self._dev_apply_selection(candidate, "OLG08H2M2M")
        except Exception:
            pass

    def _dev_apply_selection(self, file_path: str, assembly_code: str):
        """Apply file and code selection programmatically (shared by dev features)."""
        # Mark dev mode active and set output directory to project root / DEV TESTING
        try:
            self.dev_mode_active = True
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            dev_dir = os.path.join(project_root, "DEV TESTING")
            os.makedirs(dev_dir, exist_ok=True)
            os.environ['SOLID_OUTPUT_DIR'] = dev_dir
            # Set OLZ reference file for verification
            os.environ['SOLID_OLZ_REFERENCE_FILE'] = r"P:\GUINCHOS E GUINDASTES\OL1 - GERENCIAMENTO DE PROJETO\TODOS CADASTRADOS.csv"
        except Exception:
            pass
        # Set selected file
        self.selected_input_file = file_path
        # Update entry display with filename only
        filename = os.path.basename(file_path)
        self.file_path_entry.config(state="normal")
        self.file_path_entry.delete(0, tk.END)
        self.file_path_entry.insert(0, filename)
        self.file_path_entry.config(state="readonly")
        # Prefill assembly code
        self.assembly_code_entry.delete(0, tk.END)
        self.assembly_code_entry.insert(0, assembly_code)
        self.assembly_code_valid = True
        # Update state and UI
        self._update_state_tracking()
        self._update_convert_button_state()
        self._update_status_indicator("✅ Modo DEV: arquivo de exemplo carregado", self.colors['success'])

    def _dev_prefill_example(self):
        """Handler for DEV button to pre-select example file and code."""
        try:
            candidate = os.path.join(os.path.dirname(__file__), "..", "..", "EXEMPLO LISTA DE MONTAGEM.xlsx")
            candidate = os.path.abspath(candidate)
            if os.path.exists(candidate):
                self._dev_apply_selection(candidate, "OLG08H2M2M")
            else:
                messagebox.showwarning("DEV", "Arquivo de exemplo não encontrado na raiz do projeto.")
        except Exception as e:
            messagebox.showerror("DEV", f"Falha ao aplicar seleção de exemplo: {str(e)}")
    
    def _create_ui(self):
        """Create the user interface components."""
        # Main container with dark theme padding - centered
        main_container = tk.Frame(self.root, bg=self.colors['light'], padx=30, pady=20)
        main_container.pack(expand=True, fill='both')
        
        # Center the main content
        center_frame = tk.Frame(main_container, bg=self.colors['light'])
        center_frame.pack(expand=True, fill='both')
        
        # Main content frame with dark theme border - centered
        self.main_frame = tk.Frame(center_frame, bg=self.colors['gray_100'], relief="raised", bd=2, padx=25, pady=20)
        self.main_frame.pack(expand=False, fill='both', anchor='center')
        
        # Create UI sections
        self._create_header_section()
        self._create_file_section()
        self._create_config_section()
        self._create_conversion_type_section()
        self._create_buttons_section()
        self._create_status_indicator()
    
    def _create_header_section(self):
        """Create the header section with logo and title."""
        # Header section - dark theme - centered
        header_frame = tk.Frame(self.main_frame, bg=self.colors['gray_100'])
        header_frame.pack(fill='x', pady=(0, 15))
        
        # Center all header content
        header_center = tk.Frame(header_frame, bg=self.colors['gray_100'])
        header_center.pack(expand=True, fill='x')
    
    def _create_file_section(self):
        """Create the file selection section."""
        # File selection section - dark theme - centered
        file_section_frame = tk.Frame(self.main_frame, bg=self.colors['gray_100'])
        file_section_frame.pack(fill='x', pady=(10, 15))
        
        # Center the file section
        file_center = tk.Frame(file_section_frame, bg=self.colors['gray_100'])
        file_center.pack(expand=True, fill='x')
        
        # File section with dark theme border - centered
        file_container = tk.Frame(file_center, bg=self.colors['gray_100'], relief="groove", bd=1, padx=20, pady=15)
        file_container.pack(fill='x')
        
        tk.Label(file_container, 
                text="📁 Arquivo de Estrutura de Montagem (XLSX)", 
                font=("Arial", 12, "bold"),
                fg=self.colors['primary'],
                bg=self.colors['gray_100']).pack(anchor="center", pady=(0, 15))
        
        # Center both file field and button
        file_center_inner = tk.Frame(file_container, bg=self.colors['gray_100'])
        file_center_inner.pack(expand=True, fill='x')
        
        # File input frame - centered
        file_input_frame = tk.Frame(file_center_inner, bg=self.colors['gray_100'])
        file_input_frame.pack(anchor='center', pady=(0, 15))
        
        self.file_path_entry = ttk.Entry(file_input_frame, 
                                        font=("Arial", 12), 
                                        state="readonly", 
                                        style="DarkEntry.TEntry",
                                        width=30,
                                        justify='center')
        self.file_path_entry.pack(ipady=6, ipadx=10)
        
        # Button frame - centered below field
        button_frame = tk.Frame(file_center_inner, bg=self.colors['gray_100'])
        button_frame.pack(anchor='center')
        
        self.browse_button = tk.Button(button_frame, 
                                      text="📂 Procurar...", 
                                      command=self._browse_file,
                                      font=("Arial", 12),
                                      bg=self.colors['secondary'], 
                                      fg=self.colors['gray_900'],
                                      relief="solid",
                                      bd=1,
                                      padx=25, 
                                      pady=8,
                                      cursor="hand2")
        self.browse_button.pack(side=tk.LEFT)

        # Small DEV helper button to pre-select example file and fill code
        self.dev_prefill_button = tk.Button(button_frame,
                                           text="🔧 DEV",
                                           command=self._dev_prefill_example,
                                           font=("Arial", 10, "bold"),
                                           bg=self.colors['gray_300'],
                                           fg=self.colors['gray_900'],
                                           relief="solid",
                                           bd=1,
                                           padx=10,
                                           pady=6,
                                           cursor="hand2")
        self.dev_prefill_button.pack(side=tk.LEFT, padx=(8, 0))
        
        # Add hover effects to browse button
        self._add_hover_effects(self.browse_button, self.colors['secondary'], self.colors['primary'])
        self._add_hover_effects(self.dev_prefill_button, self.colors['gray_300'], self.colors['secondary'])
    
    def _create_conversion_type_section(self):
        """Create the conversion type selection section."""
        # Conversion type section - dark theme - centered
        type_section_frame = tk.Frame(self.main_frame, bg=self.colors['gray_100'])
        type_section_frame.pack(fill='x', pady=(10, 15))
        
        # Center the conversion type section
        type_center = tk.Frame(type_section_frame, bg=self.colors['gray_100'])
        type_center.pack(expand=True, fill='x')
        
        # Conversion type container with dark theme border - centered
        type_container = tk.Frame(type_center, bg=self.colors['gray_100'], relief="groove", bd=1, padx=20, pady=15)
        type_container.pack(fill='x')
        
        tk.Label(type_container, 
                text="🔧 Tipo de Conversão", 
                font=("Arial", 12, "bold"),
                fg=self.colors['primary'],
                bg=self.colors['gray_100']).pack(anchor="center", pady=(0, 15))
        
        # Create conversion type selection
        self._create_conversion_type_selection(type_container)
    
    def _create_conversion_type_selection(self, parent):
        """Create the conversion type selection interface with two columns."""
        # Main frame for radio buttons
        radio_frame = tk.Frame(parent, bg=self.colors['gray_100'])
        radio_frame.pack(fill='x', pady=(0, 10))
        
        # Get conversion types for GUI (ordered to place OLZ at left and 'Todas' at right)
        conversion_types = get_conversion_types_for_gui()
        
        # Create radio buttons variable
        self.conversion_type_var = tk.StringVar(value=ConversionType.HIERARCHICAL_STRUCTURE.value)
        
        # Create two columns
        left_frame = tk.Frame(radio_frame, bg=self.colors['gray_100'])
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        right_frame = tk.Frame(radio_frame, bg=self.colors['gray_100'])
        right_frame.pack(side='right', fill='both', expand=True, padx=(10, 0))
        
        # Split conversion types into two columns
        mid_point = len(conversion_types) // 2
        left_types = conversion_types[:mid_point]
        right_types = conversion_types[mid_point:]
        
        # Create radio buttons for left column
        for name, description, conversion_type in left_types:
            self._create_radio_button_group(left_frame, name, description, conversion_type)
        
        # Create radio buttons for right column
        for name, description, conversion_type in right_types:
            self._create_radio_button_group(right_frame, name, description, conversion_type)
    
    def _create_radio_button_group(self, parent, name, description, conversion_type):
        """Create a radio button group with improved visual feedback."""
        # Container frame for this option
        option_frame = tk.Frame(parent, bg=self.colors['gray_100'], relief="groove", bd=1)
        option_frame.pack(fill='x', pady=3, padx=2)
        
        # Radio button
        radio_btn = tk.Radiobutton(
            option_frame,
            text=name,
            variable=self.conversion_type_var,
            value=conversion_type.value,
            command=self._on_conversion_type_change,
            font=("Arial", 10, "bold"),
            fg=self.colors['primary'],
            bg=self.colors['gray_100'],
            activebackground=self.colors['gray_100'],
            selectcolor=self.colors['primary'],
            indicatoron=1,
            width=25,
            anchor='w'
        )
        radio_btn.pack(anchor='w', pady=(5, 2), padx=5)
        
        # Add additional bind to ensure event is captured
        radio_btn.bind('<Button-1>', lambda e: self._on_conversion_type_change())
        
        # Description label
        desc_label = tk.Label(
            option_frame,
            text=description,
            font=("Arial", 8),
            fg=self.colors['gray_600'],
            bg=self.colors['gray_100'],
            wraplength=200,
            justify='left'
        )
        desc_label.pack(anchor='w', pady=(0, 5), padx=5)
        
        # Store references for visual feedback
        if not hasattr(self, 'radio_button_groups'):
            self.radio_button_groups = {}
        
        self.radio_button_groups[conversion_type] = {
            'frame': option_frame,
            'radio': radio_btn,
            'description': desc_label
        }
    
    def _on_conversion_type_change(self):
        """Handle conversion type change."""
        try:
            # Get selected conversion type
            selected_value = self.conversion_type_var.get()
            self.selected_conversion_type = ConversionType(selected_value)
            self.conversion_type_selected_by_user = True
            
            # Reset conversion state when changing conversion type
            self.conversion_completed = False
            self.last_generated_file = None
            self.current_output_file = None
            # Note: conversion_type_selected_by_user remains True after user selection
            
            # Disable open file button since we're starting fresh
            self.open_file_button.config(state=tk.DISABLED)
            
            # Update visual feedback for all radio button groups
            self._update_radio_button_visual_feedback()
            
            # Update assembly code requirement
            self._update_assembly_code_requirement()
            
            # Update convert button state
            self._update_convert_button_state()
            
            # Button state is updated immediately above - no delay needed
            
            # Update status indicator
            self._update_status_for_conversion_type()
            
        except Exception as e:
            print(f"Error handling conversion type change: {e}")
    
    def _update_radio_button_visual_feedback(self):
        """Update visual feedback for radio button groups."""
        try:
            if hasattr(self, 'radio_button_groups'):
                for conversion_type, group in self.radio_button_groups.items():
                    frame = group['frame']
                    radio = group['radio']
                    description = group['description']
                    
                    if conversion_type == self.selected_conversion_type:
                        # Selected state - highlight
                        frame.config(
                            bg=self.colors['primary'],
                            relief="raised",
                            bd=2
                        )
                        radio.config(
                            bg=self.colors['primary'],
                            fg=self.colors['gray_900'],
                            selectcolor=self.colors['gray_900']
                        )
                        description.config(
                            bg=self.colors['primary'],
                            fg=self.colors['gray_900']
                        )
                    else:
                        # Unselected state - normal
                        frame.config(
                            bg=self.colors['gray_100'],
                            relief="groove",
                            bd=1
                        )
                        radio.config(
                            bg=self.colors['gray_100'],
                            fg=self.colors['primary'],
                            selectcolor=self.colors['primary']
                        )
                        description.config(
                            bg=self.colors['gray_100'],
                            fg=self.colors['gray_600']
                        )
        except Exception as e:
            print(f"Error updating radio button visual feedback: {e}")
    
    def _update_assembly_code_requirement(self):
        """Update UI based on assembly code requirement for selected conversion type."""
        # The assembly code is required for all conversions to compose the filename.
        # Always keep the input enabled.
        try:
            self.assembly_code_entry.config(state='normal')
        except Exception:
            pass
    
    def _update_status_for_conversion_type(self):
        """Update status indicator based on selected conversion type."""
        from ..core.conversion_types import get_conversion_type_info
        
        type_info = get_conversion_type_info(self.selected_conversion_type)
        
        if self.selected_input_file:
            if self.assembly_code_entry.get().strip():
                self._update_status_indicator(
                    f"✅ {type_info.name} - pronto para conversão", 
                    self.colors['success']
                )
            else:
                self._update_status_indicator(
                    f"⚠️ {type_info.name} - insira código da montagem", 
                    self.colors['warning']
                )
        else:
            self._update_status_indicator(
                f"📋 {type_info.name} - aguardando seleção de arquivo", 
                self.colors['gray_600']
            )
    
    def _create_config_section(self):
        """Create the configuration section."""
        # Configuration section - dark theme - centered
        config_section_frame = tk.Frame(self.main_frame, bg=self.colors['gray_100'])
        config_section_frame.pack(fill='x', pady=(0, 15))
        
        # Center the configuration section
        config_center = tk.Frame(config_section_frame, bg=self.colors['gray_100'])
        config_center.pack(expand=True, fill='x')
        
        # Configuration container with dark theme border - centered
        config_container = tk.Frame(config_center, bg=self.colors['gray_100'], relief="groove", bd=1, padx=20, pady=15)
        config_container.pack(fill='x')
        
        tk.Label(config_container, 
                text="⚙️ Código da montagem principal", 
                font=("Arial", 12, "bold"),
                fg=self.colors['primary'],
                bg=self.colors['gray_100']).pack(anchor="center", pady=(0, 15))
        
        # Assembly code section - dark theme - centered
        assembly_frame = tk.Frame(config_container, bg=self.colors['gray_100'])
        assembly_frame.pack(fill='x', pady=(0, 12))
        
        # Center the assembly code section
        assembly_center = tk.Frame(assembly_frame, bg=self.colors['gray_100'])
        assembly_center.pack(expand=True, fill='x')

        assembly_input_frame = tk.Frame(assembly_center, bg=self.colors['gray_100'])
        assembly_input_frame.pack(anchor="center")
        
        # Assembly code entry with better width
        self.assembly_code_entry = ttk.Entry(assembly_input_frame, 
                                            font=("Arial", 12),
                                            style="DarkEntry.TEntry",
                                            width=20)
        self.assembly_code_entry.pack(ipady=6, ipadx=10)
        
        # Add real-time validation for assembly code
        self.assembly_code_entry.bind('<KeyRelease>', self._on_assembly_code_change)
        self.assembly_code_entry.bind('<FocusOut>', self._on_assembly_code_focus_out)
    
    def _create_buttons_section(self):
        """Create the buttons section."""
        # Buttons section - dark theme - centered
        buttons_section_frame = tk.Frame(self.main_frame, bg=self.colors['gray_100'])
        buttons_section_frame.pack(fill='x', pady=(15, 15))
        
        # Center the buttons container
        buttons_center = tk.Frame(buttons_section_frame, bg=self.colors['gray_100'])
        buttons_center.pack(expand=True, fill='x')
        
        buttons_frame = tk.Frame(buttons_center, bg=self.colors['gray_100'])
        buttons_frame.pack(anchor='center')
        
        # Convert button
        self.convert_button = tk.Button(buttons_frame, 
                                       text="🚀 Executar Conversão", 
                                       command=self._run_conversion,
                                       font=("Arial", 13, "bold"),
                                       bg=self.colors['primary'], 
                                       fg=self.colors['gray_900'],
                                       relief="flat",
                                       padx=35, 
                                       pady=15,
                                       state=tk.DISABLED,
                                       cursor="hand2")
        self.convert_button.pack(side=tk.LEFT, padx=(0, 20))
        
        # Open file button
        self.open_file_button = tk.Button(buttons_frame, 
                                         text="📄 Abrir CSV Gerado", 
                                         command=self._open_generated_file,
                                         font=("Arial", 13, "bold"),
                                         bg=self.colors['secondary'], 
                                         fg=self.colors['gray_900'],
                                         relief="flat",
                                         padx=35, 
                                         pady=15,
                                         state=tk.DISABLED,
                                         cursor="hand2")
        self.open_file_button.pack(side=tk.LEFT)
        
        # Add hover effects to buttons
        self._add_hover_effects(self.convert_button, self.colors['primary'], self.colors['secondary'])
        self._add_hover_effects(self.open_file_button, self.colors['secondary'], self.colors['primary'])
    
        
    
    def _create_status_indicator(self):
        """Create the status indicator."""
        try:
            # Status indicator frame
            status_frame = tk.Frame(self.main_frame, bg=self.colors['gray_100'])
            status_frame.pack(fill='x', pady=(5, 0))
            
            # Status label
            self.status_label = tk.Label(status_frame, 
                                       text="📋 Aguardando seleção de arquivo",
                                       font=("Arial", 9),
                                       fg=self.colors['gray_600'],
                                       bg=self.colors['gray_100'])
            self.status_label.pack(anchor="center")
        except Exception:
            pass
    
    def _add_hover_effects(self, button, normal_color, hover_color):
        """Add hover effects to a button."""
        def on_enter(e):
            if button['state'] == 'normal':
                button.config(bg=hover_color)
        
        def on_leave(e):
            if button['state'] == 'normal':
                button.config(bg=normal_color)
        
        button.bind("<Enter>", on_enter)
        button.bind("<Leave>", on_leave)
    
    def _calculate_file_hash(self, file_path: str) -> Optional[str]:
        """Calculate hash of a file to detect changes."""
        try:
            import hashlib
            
            if not os.path.exists(file_path):
                return None
            
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            print(f"Error calculating file hash: {e}")
            return None
    
    def _check_for_changes(self) -> bool:
        """Check if input file or assembly code has changed since last conversion."""
        try:
            # Check if input file changed
            if self.selected_input_file:
                current_file_hash = self._calculate_file_hash(self.selected_input_file)
                if current_file_hash != self.last_input_file_hash:
                    return True
            
            # Check if assembly code changed
            current_assembly_code = self.assembly_code_entry.get().strip()
            if current_assembly_code != self.last_assembly_code:
                return True
            
            return False
        except Exception as e:
            print(f"Error checking for changes: {e}")
            return True  # Assume changes if error
    
    def _reset_conversion_state(self):
        """Reset the conversion state when changes are detected."""
        try:
            # Reset state variables
            self.conversion_completed = False
            self.current_output_file = None
            self.conversion_in_progress = False
            
            # Disable buttons
            self.open_file_button.config(state=tk.DISABLED)
            self.convert_button.config(state=tk.DISABLED)
            
            
            # Update status indicator
            if self.selected_input_file:
                self._update_status_indicator("⚠️ Mudanças detectadas - estado resetado", self.colors['warning'])
            else:
                self._update_status_indicator("📋 Aguardando seleção de arquivo")
        except Exception as e:
            print(f"Error resetting conversion state: {e}")
    
    def _update_state_tracking(self):
        """Update the state tracking variables."""
        try:
            # Update file hash if file is selected
            if self.selected_input_file:
                self.last_input_file_hash = self._calculate_file_hash(self.selected_input_file)
            
            # Update assembly code
            self.last_assembly_code = self.assembly_code_entry.get().strip()
        except Exception as e:
            print(f"Error updating state tracking: {e}")
    
    def _on_assembly_code_change(self, event):
        """Handle real-time changes in assembly code field."""
        try:
            # Get current text
            current_text = self.assembly_code_entry.get()
            
            # Sanitize the input
            sanitized_text, is_valid = self.assembly_validator.validate_assembly_code_input(current_text)
            
            # Update the field if text was changed
            if sanitized_text != current_text:
                # Store cursor position
                cursor_pos = self.assembly_code_entry.index(tk.INSERT)
                
                # Update the text
                self.assembly_code_entry.delete(0, tk.END)
                self.assembly_code_entry.insert(0, sanitized_text)
                
                # Restore cursor position (adjusted for length change)
                new_cursor_pos = min(cursor_pos, len(sanitized_text))
                self.assembly_code_entry.icursor(new_cursor_pos)
            
            # Update validation state
            self.assembly_code_valid = True
            
            # Update field appearance based on validation
            self._update_assembly_code_appearance()
            
            # Update convert button state based on current inputs
            self._update_convert_button_state()
            
            # Do not reset conversion state while typing; just track changes
            self._update_state_tracking()
        except Exception as e:
            print(f"Error in assembly code validation: {e}")
    
    def _on_assembly_code_focus_out(self, event):
        """Handle focus out event for assembly code field."""
        try:
            # Final validation and cleanup
            current_text = self.assembly_code_entry.get()
            sanitized_text, is_valid = self.assembly_validator.validate_assembly_code_input(current_text)
            
            if sanitized_text != current_text:
                self.assembly_code_entry.delete(0, tk.END)
                self.assembly_code_entry.insert(0, sanitized_text)
            
            self.assembly_code_valid = True
            self._update_assembly_code_appearance()
            
            # Update convert button state
            self._update_convert_button_state()
            # Track new value
            self._update_state_tracking()
        except Exception as e:
            print(f"Error in assembly code focus out: {e}")
    
    def _update_assembly_code_appearance(self):
        """Update the visual appearance of the assembly code field based on validation."""
        try:
            current_text = self.assembly_code_entry.get()
            
            if not current_text:
                # Empty field - normal appearance
                self.assembly_code_entry.configure(style="DarkEntry.TEntry")
            elif self.assembly_code_valid:
                # Valid field - green border
                self.style.configure("ValidEntry.TEntry",
                                   fieldbackground=self.colors['gray_200'],
                                   foreground="black",
                                   insertcolor="black",
                                   borderwidth=2,
                                   relief="solid",
                                   bordercolor="#28a745")  # Green border
                self.assembly_code_entry.configure(style="ValidEntry.TEntry")
            else:
                # Invalid field - red border
                self.style.configure("InvalidEntry.TEntry",
                                   fieldbackground=self.colors['gray_200'],
                                   foreground="black",
                                   insertcolor="black",
                                   borderwidth=2,
                                   relief="solid",
                                   bordercolor="#dc3545")  # Red border
                self.assembly_code_entry.configure(style="InvalidEntry.TEntry")
        except Exception as e:
            print(f"Error updating assembly code appearance: {e}")
    
    def _update_convert_button_state(self):
        """Update the convert button state based on current conditions."""
        try:
            # Don't enable button if conversion is in progress
            if self.conversion_in_progress:
                self.convert_button.config(state=tk.DISABLED)
                return
            
            # Button should be enabled only if:
            # 1. A file is selected
            # 2. A conversion type has been selected by user
            # 3. Assembly code field is not empty (if required by conversion type)
            # 4. Conversion is not completed (or state was reset)
            
            file_selected = bool(self.selected_input_file and os.path.exists(self.selected_input_file))
            type_selected = self.conversion_type_selected_by_user
            not_completed = not self.conversion_completed
            
            # Assembly code is now required for all conversion types
            code_not_empty = bool(self.assembly_code_entry.get().strip())
            should_enable = file_selected and type_selected and code_not_empty and not_completed
            
            if should_enable:
                self.convert_button.config(state=tk.NORMAL)
            else:
                self.convert_button.config(state=tk.DISABLED)
        except Exception as e:
            print(f"Error updating convert button state: {e}")
    
    def _run_all_conversions(self):
        """Execute all conversions in sequence, ending with OLZ verification."""
        try:
            if not self.selected_input_file or not os.path.exists(self.selected_input_file):
                messagebox.showerror("Erro", "Nenhum arquivo selecionado ou arquivo não encontrado.")
                return
            
            if not self.assembly_code_entry.get().strip():
                messagebox.showerror("Erro", "Código da montagem principal é obrigatório.")
                return
            
            # Disable buttons during execution
            self.convert_button.config(state=tk.DISABLED)
            self.open_file_button.config(state=tk.DISABLED)
            
            # Create specific folder for "Todas as Conversões"
            assembly_code = self.assembly_code_entry.get().strip()
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            if getattr(self, 'dev_mode_active', False):
                # In dev mode, use DEV TESTING folder
                base_dir = os.path.join(project_root, "DEV TESTING")
            else:
                # In normal mode, use the input file directory
                base_dir = os.path.dirname(self.selected_input_file)
            
            # Create "CADASTRO COMPLETO [código]" folder
            complete_folder = os.path.join(base_dir, f"CADASTRO COMPLETO {assembly_code}")
            os.makedirs(complete_folder, exist_ok=True)
            
            # Set environment variable for this specific execution
            original_output_dir = os.environ.get('SOLID_OUTPUT_DIR')
            os.environ['SOLID_OUTPUT_DIR'] = complete_folder
            
            # Set conversion in progress
            self.conversion_in_progress = True
            self._update_status_indicator("🔄 Executando todas as conversões...", self.colors['warning'])
            
            # Define conversion sequence (excluding hierarchical structure and OLZ verification)
            conversion_sequence = [
                ConversionType.PARTS_REGISTRATION,
                ConversionType.DESCRIPTION_UPDATE,
                ConversionType.MATERIAL_UPDATE,
                ConversionType.OLZ_VERIFICATION
            ]
            
            results = []
            assembly_code = self.assembly_code_entry.get().strip()
            
            # Execute each conversion
            for i, conversion_type in enumerate(conversion_sequence, 1):
                try:
                    self._update_status_indicator(f"🔄 Executando conversão {i}/{len(conversion_sequence)}: {conversion_type.value}...", self.colors['warning'])
                    
                    # Create conversion request
                    request = ConversionRequest(
                        input_file=self.selected_input_file,
                        output_file="",  # Will be set by converter
                        assembly_code=assembly_code
                    )
                    
                    # Execute conversion and show individual result
                    result = self._execute_conversion_now(request, conversion_type)
                    
                    # Show individual conversion result
                    if result.success:
                        self._show_conversion_result(
                            result.success, 
                            result.message, 
                            result.output_file, 
                            assembly_code, 
                            getattr(result, 'stats', None)
                        )
                    else:
                        messagebox.showerror(f"Erro - {conversion_type.value}", result.message)
                    
                    results.append({
                        'type': conversion_type,
                        'success': result.success,
                        'message': result.message,
                        'output_file': result.output_file
                    })
                    
                    if not result.success:
                        self._update_status_indicator(f"❌ Erro na conversão {conversion_type.value}: {result.message}", self.colors['danger'])
                        break
                    
                except Exception as e:
                    error_msg = f"Erro na conversão {conversion_type.value}: {str(e)}"
                    results.append({
                        'type': conversion_type,
                        'success': False,
                        'message': error_msg,
                        'output_file': None
                    })
                    self._update_status_indicator(f"❌ {error_msg}", self.colors['danger'])
                    break
            
            # Generate summary message
            successful = [r for r in results if r['success']]
            failed = [r for r in results if not r['success']]
            
            summary_message = f"🔄 Execução de todas as conversões concluída!\n\n"
            summary_message += f"✅ Sucessos: {len(successful)}/{len(conversion_sequence)}\n"
            summary_message += f"📁 Pasta criada: {complete_folder}\n"
            
            if successful:
                summary_message += f"\n📄 Arquivos gerados:\n"
                for result in successful:
                    if result['output_file']:
                        filename = os.path.basename(result['output_file'])
                        summary_message += f"• {result['type'].value}: {filename}\n"
            
            if failed:
                summary_message += f"\n❌ Falhas:\n"
                for result in failed:
                    summary_message += f"• {result['type'].value}: {result['message']}\n"
            
            # Restore original output directory
            if original_output_dir is not None:
                os.environ['SOLID_OUTPUT_DIR'] = original_output_dir
            elif 'SOLID_OUTPUT_DIR' in os.environ:
                del os.environ['SOLID_OUTPUT_DIR']
            
            # Update UI state
            self.conversion_completed = True
            self.conversion_in_progress = False
            
            # Enable buttons
            self.convert_button.config(state=tk.NORMAL)
            self.open_file_button.config(state=tk.NORMAL)
            
            # Update status
            if failed:
                self._update_status_indicator("⚠️ Execução concluída com erros", self.colors['warning'])
            else:
                self._update_status_indicator("✅ Todas as conversões executadas com sucesso!", self.colors['success'])
            
            # Show summary
            messagebox.showinfo("Execução Concluída", summary_message)
            
        except Exception as e:
            error_msg = f"Erro durante execução de todas as conversões: {str(e)}"
            self._update_status_indicator(f"❌ {error_msg}", self.colors['danger'])
            messagebox.showerror("Erro", error_msg)
            
            # Restore original output directory
            if 'original_output_dir' in locals() and original_output_dir is not None:
                os.environ['SOLID_OUTPUT_DIR'] = original_output_dir
            elif 'original_output_dir' in locals() and 'SOLID_OUTPUT_DIR' in os.environ:
                del os.environ['SOLID_OUTPUT_DIR']
            
            # Re-enable buttons
            self.conversion_in_progress = False
            self.convert_button.config(state=tk.NORMAL)
            self.open_file_button.config(state=tk.NORMAL)
    
    def _update_status_indicator(self, message: str, color: str = None):
        """Update the status indicator message and color."""
        try:
            if hasattr(self, 'status_label'):
                self.status_label.config(text=message)
                if color:
                    self.status_label.config(fg=color)
                else:
                    self.status_label.config(fg=self.colors['gray_600'])
        except Exception as e:
            print(f"Error updating status indicator: {e}")
    
    def _schedule_file_check(self):
        """Schedule periodic file change checks."""
        # Removed periodic checks - now using event-based triggers only
        pass
    
    def _browse_file(self):
        """Open file dialog to select structure file."""
        try:
            from ..core.validators import ValidationService
            
            input_file = filedialog.askopenfilename(
                title="Selecionar Arquivo de Estrutura de Montagem",
                filetypes=[
                    ("Arquivos Excel", "*.xlsx *.xls"),
                    ("Todos os arquivos", "*.*")
                ]
            )
            
            if input_file:
                # Validate the selected file
                validator = ValidationService()
                validation_result = validator.file_validator.validate_file_path(input_file)
                
                if not validation_result.is_valid:
                    error_msg = "Arquivo inválido:\n" + "\n".join(validation_result.errors)
                    messagebox.showerror("Arquivo Inválido", error_msg)
                    return
                
                # Show warnings if any
                if validation_result.warnings:
                    warning_msg = "Avisos sobre o arquivo selecionado:\n" + "\n".join(validation_result.warnings)
                    messagebox.showwarning("Avisos", warning_msg)
                
                # Check if this is a different file than before
                if input_file != self.selected_input_file:
                    # Reset conversion state when file changes
                    self._reset_conversion_state()
                
                self.selected_input_file = input_file
                # Show only filename in the entry for better UX
                filename = os.path.basename(input_file)
                
                # Update the entry field
                self.file_path_entry.config(state="normal")
                self.file_path_entry.delete(0, tk.END)
                self.file_path_entry.insert(0, filename)
                self.file_path_entry.config(state="readonly")
                
                # Update convert button state based on current conditions
                self._update_convert_button_state()
                
                # Update state tracking
                self._update_state_tracking()
                
                # Update status indicator
                if self.assembly_code_entry.get().strip():
                    self._update_status_indicator("✅ Arquivo selecionado - pronto para conversão", self.colors['success'])
                else:
                    self._update_status_indicator("⚠️ Arquivo selecionado - insira código da montagem", self.colors['warning'])
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao selecionar arquivo: {str(e)}")
    
    def _open_generated_file(self):
        """Open the last generated CSV file with default application."""
        try:
            candidate = None
            # Prefer explicitly tracked last generated file
            if getattr(self, 'last_generated_file', None) and os.path.exists(self.last_generated_file):
                candidate = self.last_generated_file
            else:
                # Fallback: search for newest generated ESTRUTURA_*.csv near input file or working dir
                search_dirs = []
                if getattr(self, 'selected_input_file', None):
                    base_dir = os.path.dirname(self.selected_input_file)
                    # Include potential structured folder "ESTRUTURA <code>"
                    try:
                        for name in os.listdir(base_dir):
                            if name.upper().startswith("ESTRUTURA "):
                                path = os.path.join(base_dir, name)
                                if os.path.isdir(path):
                                    search_dirs.append(path)
                    except Exception:
                        pass
                    search_dirs.append(base_dir)
                # Also add current working directory as last resort
                search_dirs.append(os.getcwd())
                newest_time = -1
                for d in search_dirs:
                    try:
                        for fname in os.listdir(d):
                            if fname.upper().startswith("ESTRUTURA_") and fname.lower().endswith(".csv"):
                                fpath = os.path.join(d, fname)
                                mtime = os.path.getmtime(fpath)
                                if mtime > newest_time:
                                    newest_time = mtime
                                    candidate = fpath
                    except Exception:
                        continue
            if candidate and os.path.exists(candidate):
                os.startfile(candidate)
                # Update reference for future opens
                self.last_generated_file = candidate
                self.open_file_button.config(state=tk.NORMAL)
            else:
                messagebox.showwarning("Aviso", "Nenhum arquivo gerado encontrado.")
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível abrir o arquivo:\n{str(e)}")
    
    def _run_conversion(self):
        """Start the conversion process with progress simulation"""
        try:
            # Check if file is selected
            if not self.selected_input_file:
                messagebox.showwarning("Arquivo Necessário", "Por favor, selecione uma estrutura de montagem primeiro usando 'Procurar...'.")
                return
            
            # Validate file still exists
            if not os.path.exists(self.selected_input_file):
                messagebox.showerror("Arquivo Não Encontrado", f"O arquivo selecionado não foi encontrado:\n{self.selected_input_file}\n\nPor favor, selecione um novo arquivo.")
                self.selected_input_file = None
                self.file_path_entry.config(state="normal")
                self.file_path_entry.delete(0, tk.END)
                self.file_path_entry.config(state="readonly")
                self.convert_button.config(state=tk.DISABLED)
                return
            
            input_file = self.selected_input_file
            
            # Get assembly code from user input (required)
            assembly_code = self.assembly_code_entry.get().strip()
            
            # Check if field is empty
            if not assembly_code:
                messagebox.showerror("Campo Obrigatório", "O código da montagem principal é obrigatório. Por favor, insira o código no campo correspondente.")
                self.assembly_code_entry.focus()
                return
            
            # Validate output directory is writable
            directory, _ = os.path.split(input_file)
            try:
                # Test if directory is writable
                test_file = os.path.join(directory, "test_write.tmp")
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
            except Exception as e:
                messagebox.showerror("Erro de Permissão", f"Não é possível escrever no diretório:\n{directory}\n\nErro: {str(e)}")
                return
            
            # Generate output filename with ESTRUTURA format
            code_for_filename = assembly_code
            output_file = os.path.join(directory, f"ESTRUTURA_{code_for_filename}.csv")
            
            # Check if output file already exists
            if os.path.exists(output_file):
                response = messagebox.askyesno("Arquivo Existente", f"O arquivo de saída já existe:\n{os.path.basename(output_file)}\n\nDeseja sobrescrever?")
                if not response:
                    return
            
            # Check for changes before starting conversion
            if self._check_for_changes():
                self._reset_conversion_state()
            
            # If selection is 'Todas as Conversões', use the all-conversions runner
            if (hasattr(self.selected_conversion_type, 'name') and self.selected_conversion_type.name == 'ALL_CONVERSIONS') or self.selected_conversion_type == ConversionType.ALL_CONVERSIONS:
                self._run_all_conversions()
                return

            # In DEV mode, run conversion immediately without illustrative progress
            if getattr(self, 'dev_mode_active', False):
                request = ConversionRequest(
                    input_file=input_file,
                    output_file=output_file,
                    assembly_code=assembly_code
                )
                self._execute_conversion_now(request)
            else:
                # Start progress simulation
                self._start_progress_simulation(input_file, output_file, assembly_code)
            
        except Exception as e:
            messagebox.showerror("Erro", f"Erro inesperado: {str(e)}")
    
    def _start_progress_simulation(self, input_file, output_file, assembly_code):
        """Start realistic progress simulation based on file size"""
        # Set conversion in progress flag and disable convert button
        self.conversion_in_progress = True
        self.convert_button.config(state=tk.DISABLED)
        
        # Get file line count for realistic timing
        try:
            import pandas as pd
            df = pd.read_excel(input_file)
            line_count = len(df)
            # Calculate time: lines/100 seconds, minimum 2 seconds, maximum 10 seconds
            processing_time = max(2, min(10, line_count / 100))
        except:
            line_count = 100
            processing_time = 3
        
        # Execute conversion directly
        self._execute_conversion_direct(input_file, output_file, assembly_code)
    
    def _execute_conversion_direct(self, input_file, output_file, assembly_code):
        """Execute conversion directly without progress simulation."""
        try:
            # Use multi-type converter
            request = ConversionRequest(
                input_file=input_file,
                output_file=output_file,
                assembly_code=assembly_code
            )
            
            result = self.multi_converter.convert(request, self.selected_conversion_type)
            success = result.success
            message = result.message
            # Prefer the output file path returned by the converter (may differ by type)
            actual_output_file = getattr(result, 'output_file', None) or output_file
            
            # Re-enable convert button
            self.convert_button.config(state=tk.NORMAL)
            
            # Show result
            self._show_conversion_result(success, message, actual_output_file, assembly_code, getattr(result, 'stats', None))
            
        except Exception as e:
            messagebox.showerror("Erro", f"Erro na conversão: {str(e)}")
            self.convert_button.config(state=tk.NORMAL)

    def _execute_conversion_now(self, request, conversion_type=None):
        """Run conversion immediately without progress animation (DEV mode)."""
        try:
            # Use provided conversion_type or fall back to selected one
            target_conversion_type = conversion_type or self.selected_conversion_type
            result = self.multi_converter.convert(request, target_conversion_type)
            
            # Return result for use in _run_all_conversions
            return result
        except Exception as e:
            error_msg = f"Erro na conversão (DEV): {str(e)}"
            messagebox.showerror("Erro", error_msg)
            # Return a failed result
            from ..core.models import ConversionResult
            return ConversionResult(success=False, message=error_msg)
    
    def _show_conversion_result(self, success, message, output_file, assembly_code, stats=None):
        """Show the conversion result after progress is complete"""
        if success:
            # Store the generated file path and enable the open button
            self.last_generated_file = output_file
            self.open_file_button.config(state=tk.NORMAL)
            
            # Update conversion state
            self.conversion_completed = True
            self.current_output_file = output_file
            self.conversion_in_progress = False
            
            # Disable convert button after successful conversion
            self.convert_button.config(state=tk.DISABLED)
            
            # Update state tracking after successful conversion
            self._update_state_tracking()
            
            # Update status indicator
            self._update_status_indicator("✅ Conversão concluída com sucesso!", self.colors['success'])
            
            from ..core.conversion_types import ConversionType
            current_type = self.selected_conversion_type

            # If hierarchical structure, build the detailed message with stats and Z info
            if current_type == ConversionType.HIERARCHICAL_STRUCTURE:
                # Check if Z was detected and show warning
                has_z_warning = "⚠️ AVISO - DETECÇÃO DE 'Z'" in message
                
                # Extract Z detection info
                z_info_section = ""
                if "⚠️ AVISO - DETECÇÃO DE 'Z'" in message:
                    z_start = message.find("⚠️ AVISO - DETECÇÃO DE 'Z'")
                    z_info_section = f"\n\n{message[z_start:]}"
                elif "✅ VERIFICAÇÃO DE 'Z'" in message:
                    z_start = message.find("✅ VERIFICAÇÃO DE 'Z'")
                    z_info_section = f"\n\n{message[z_start:]}"
                
                # Get filename for display
                filename = os.path.basename(output_file)
                code_for_filename = assembly_code
                
                # Safely extract statistics section from message
                try:
                    if ("Verificação OK." in message) and ("Pronto para importação" in message):
                        stats_section = message.split("Verificação OK.", 1)[1].split("Pronto para importação", 1)[0].strip()
                    else:
                        stats_section = message.strip()
                except Exception:
                    stats_section = message.strip()

                detailed_message = f"""✅ EXPORTAÇÃO CONCLUÍDA COM SUCESSO!

📁 Arquivo CSV gerado:
{filename}

📊 Estatísticas da Conversão:
{stats_section}

📋 Arquivos Criados:
• ESTRUTURA_{code_for_filename}.csv (estrutura principal)
• RELATORIO_REMOVIDOS_{code_for_filename}.csv (relatório de exclusões)

🚀 Próximos Passos:
1. Use 'Abrir CSV Gerado' para visualizar a estrutura
2. Verifique o relatório de removidos se necessário
3. Importe o CSV no sistema NEO

✨ A estrutura está pronta para importação no sistema NEO!{z_info_section}"""

                messagebox.showinfo("Exportação Concluída", detailed_message)

                if has_z_warning:
                    # Safely extract Z warning details
                    try:
                        if "⚠️ AVISO - DETECÇÃO DE 'Z' NO ARQUIVO CSV GERADO:" in z_info_section:
                            z_details = z_info_section.split("⚠️ AVISO - DETECÇÃO DE 'Z' NO ARQUIVO CSV GERADO:", 1)[1].strip()
                        else:
                            z_details = z_info_section.strip()
                    except Exception:
                        z_details = z_info_section.strip()

                    z_warning_message = f"""⚠️ AVISO - DETECÇÃO DE 'Z' NO ARQUIVO CSV GERADO!

{z_details}

🔍 AÇÃO RECOMENDADA:
• Verifique as entradas listadas acima
• Confirme se os códigos com 'Z' estão corretos
• Revise a estrutura antes da importação no NEO

⚠️ Este aviso não impede a exportação, mas requer atenção!"""
                    messagebox.showwarning("⚠️ AVISO - Detecção de 'Z'", z_warning_message)
            else:
                # For other conversion types, show the message returned by the converter as-is
                messagebox.showinfo("Exportação Concluída", message)

            # Follow-up warnings popup if any
            try:
                if stats and getattr(stats, 'warnings', None):
                    warnings_list = stats.warnings
                    preview = "\n".join([f"• {w}" for w in warnings_list[:20]])
                    if len(warnings_list) > 20:
                        preview += f"\n• ... e mais {len(warnings_list) - 20} ocorrências"
                    messagebox.showwarning("Avisos de comprimento", f"Foram encontrados {len(warnings_list)} aviso(s):\n\n{preview}")
            except Exception:
                pass

            # After main success popup, if there are warnings in stats, show a follow-up popup with details
            try:
                # We need access to the last conversion result; reuse message and output, but warnings live in stats
                # Fetch warnings from the multi_converter last result through a simple attribute handoff isn't stored,
                # so we cannot access it directly here unless passed in. As a workaround, we add warnings to status label only if available
                # However, when using our conversion paths, result.stats.warnings is available in _simulate_progress/_execute_conversion_now
                pass
            except Exception:
                pass
        else:
            # Reset conversion in progress flag on error
            self.conversion_in_progress = False
            messagebox.showerror("Erro na Exportação", message)
