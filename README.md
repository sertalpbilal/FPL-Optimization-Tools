
# FPL Optimization Tools

This repository provides a set of tools for solving deterministic Fantasy Premier League (FPL) optimization problems. The python code uses `pandas` for data management, `sasoptpy` for building the optimization model, and `HiGHS` via `highspy` to find a solution to the model.

It allows users to:
- Automatically select the best FPL squad based on the given projection data and solver settings.
- Customize squad constraints, formation rules, transfer strategies, and more.
- Modify data sources and parameters to suit personal models or preferences.


## 🔧 Installation
### 1. Install Python
-  **Windows**:
Download Python (preferable python3.13 or later) from [python.org](https://www.python.org/downloads/).
During installation, **make sure to check the box that says `Add Python to PATH`**.

-  **macOS**:
You can install Python via [Homebrew](https://brew.sh/) if it’s not already installed:
	```bash
	brew install python
	```

### 2. Install Git

-  **Windows**:
Download from [git-scm.com](https://git-scm.com/download/win) and accept all default installation options.

-  **macOS**:
Git is usually pre-installed. If not, run
	```bash
	brew install git
	```

### 3. Clone the Repository
Open up a terminal (search for 'command prompt' in windows) and run these commands in sequence.
```bash
cd Documents
git clone https://github.com/sertalpbilal/FPL-Optimization-Tools
cd FPL-Optimization-Tools
```

### 4. Install Dependencies
We use [`uv`](https://docs.astral.sh/uv/) for dependency management.  Install `uv` and then install the necessary dependencies for this project.
```bash
pip install uv
uv sync
```
## 🚀 Running the Optimizer


1.  **Add projection data**:
Place your projections file (e.g., `solio.csv`) in the `data/` folder.

2.  **Configure data source**:
If you are not using the default data source, update the `datasource` field in `data/user_settings.json` to match your CSV file name. E.g. if you are using a file named `projections.csv`, then the settings file should read `"datasource": "projections"`.

3. **Edit settings**
Edit any desired settings in `comprehensive_settings.json` or `user_settings.json`.  The majority of useful settings for most people will be in `user_settings.json`, with `comprehensive_settings.json` providing a wider range of options that will be used as default settings unless altered in `user_settings.json`. Details of what each setting does can be found in the .md file in the `/data/` folder.

5.  **Run the solver**:
	```bash
	cd run
	uv run python solve.py
	```

## Videos
There is a playlist [here](https://www.youtube.com/playlist?list=PLrIyJJU8_viOags1yudB_wyafRuTNs1Ed) , made by Sertalp, of the early stages of this tool, walking through how it was built and discussing ideas around optimization with a focus on FPL.

## Issues
If you have issues, feel free to open an issue on github and I will get back to you as soon as possible. Alternatively, you're welcome to email me at chris.musson@hotmail.com
