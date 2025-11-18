#!/usr/bin/env python3
"""
Project Structure Creation Script
Creates the complete BIM automation system directory structure.
"""

import os
from pathlib import Path
from typing import Dict, List

# Base directory
BASE_DIR = Path("/home/user/projektant-software")

# Complete directory structure
DIRECTORIES = [
    # Backend structure
    "projektant-copilot/backend/app",
    "projektant-copilot/backend/app/models",
    "projektant-copilot/backend/app/schemas",
    "projektant-copilot/backend/app/api",
    "projektant-copilot/backend/app/api/v1",
    "projektant-copilot/backend/app/api/v1/endpoints",
    "projektant-copilot/backend/app/services/rag",
    "projektant-copilot/backend/app/services/graph",
    "projektant-copilot/backend/app/services/compliance",
    "projektant-copilot/backend/app/services/documentation",
    "projektant-copilot/backend/app/services/ml",
    "projektant-copilot/backend/app/db",
    "projektant-copilot/backend/app/core",
    "projektant-copilot/backend/app/utils",
    "projektant-copilot/backend/alembic/versions",
    "projektant-copilot/backend/tests/unit",
    "projektant-copilot/backend/tests/integration",
    "projektant-copilot/backend/tests/e2e",
    "projektant-copilot/backend/scripts",
    "projektant-copilot/backend/ml_models",
    "projektant-copilot/backend/data/csn_samples",

    # Plugin structure
    "projektant-copilot/plugin/ProjektantCopilot/Properties",
    "projektant-copilot/plugin/ProjektantCopilot/Commands",
    "projektant-copilot/plugin/ProjektantCopilot/Services/Core",
    "projektant-copilot/plugin/ProjektantCopilot/Services/Analysis",
    "projektant-copilot/plugin/ProjektantCopilot/Services/Compliance",
    "projektant-copilot/plugin/ProjektantCopilot/Services/Documentation",
    "projektant-copilot/plugin/ProjektantCopilot/Models",
    "projektant-copilot/plugin/ProjektantCopilot/UI/ViewModels",
    "projektant-copilot/plugin/ProjektantCopilot/UI/Views",
    "projektant-copilot/plugin/ProjektantCopilot/UI/Controls",
    "projektant-copilot/plugin/ProjektantCopilot/UI/Converters",
    "projektant-copilot/plugin/ProjektantCopilot/Utils",
    "projektant-copilot/plugin/ProjektantCopilot/Resources/Icons",
    "projektant-copilot/plugin/ProjektantCopilot/Resources/Images",
    "projektant-copilot/plugin/ProjektantCopilot.Tests",

    # Docker
    "projektant-copilot/docker/init-scripts",

    # Documentation
    "projektant-copilot/docs/architecture/diagrams",
    "projektant-copilot/docs/user_guide/screenshots",
    "projektant-copilot/docs/developer",
    "projektant-copilot/docs/research",

    # GitHub workflows
    "projektant-copilot/.github/workflows",
]

# File templates
FILE_TEMPLATES = {
    "__init__.py": '"""{module_doc}"""\n',
    "base.py": '"""{module_doc}"""\n\nfrom typing import Any\n\n# TODO: Implement base classes\n',
}

def create_python_file(path: Path, module_name: str, doc: str):
    """Create a Python file with proper structure."""
    content = f'"""\n{doc}\n"""\n\nfrom typing import Any, Dict, List, Optional\nimport logging\n\nlogger = logging.getLogger(__name__)\n\n# TODO: Implement {module_name}\n'
    path.write_text(content)

def create_csharp_file(path: Path, class_name: str, doc: str):
    """Create a C# file with proper structure."""
    content = f'''using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;

namespace ProjektantCopilot
{{
    /// <summary>
    /// {doc}
    /// </summary>
    public class {class_name}
    {{
        // TODO: Implement {class_name}
    }}
}}
'''
    path.write_text(content)

def main():
    """Create the complete project structure."""

    print("Creating BIM Automation System Project Structure...")
    print("=" * 60)

    # Create all directories
    for dir_path in DIRECTORIES:
        full_path = BASE_DIR / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print(f"✓ Created directory: {dir_path}")

    # Create Python __init__.py files
    python_dirs = [d for d in DIRECTORIES if 'backend' in d and not any(x in d for x in ['alembic', 'tests', 'scripts', 'ml_models', 'data'])]
    for dir_path in python_dirs:
        full_path = BASE_DIR / dir_path / "__init__.py"
        if not full_path.exists():
            module_name = dir_path.split('/')[-1]
            create_python_file(full_path, module_name, f"{module_name.title()} module.")
            print(f"✓ Created: {dir_path}/__init__.py")

    print("\n" + "=" * 60)
    print(f"✓ Project structure created successfully!")
    print(f"✓ Total directories: {len(DIRECTORIES)}")
    print("\nNext: Creating core implementation files...")

if __name__ == "__main__":
    main()
