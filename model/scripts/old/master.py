import subprocess

# Define a dictionary mapping user-friendly names to script filenames
scripts = {
    "1": "C:/Users/erknud3/fpl-optimization/model/scripts/src/new_season.py",
    "2": "C:/Users/erknud3/fpl-optimization/model/scripts/src/teams_new_season.py",
    "3": "C:/Users/erknud3/fpl-optimization/model/scripts/src/mins_new_season.py",
    "4": "C:/Users/erknud3/fpl-optimization/model/scripts/src/player_ev.py",
}

# Display options to the user
print("Select the scripts you want to run:")
print("1 - Update Player Data")
print("2 - Update Team Data")
print("3 - Update Expected Minutes")
print("4 - Update Player Expected Value")
print(
    "Enter the numbers separated by spaces (e.g., '1 2' to run the first and second scripts)"
)

# Get user input
selection = input("Your choice: ").split()

# Validate and run selected scripts
for choice in selection:
    script = scripts.get(choice)
    if script:
        print(f"Running {script}...")
        try:
            result = subprocess.run(
                ["python", script], check=True, text=True, capture_output=True
            )
            print(result.stdout)  # Print the output of the script
        except subprocess.CalledProcessError as e:
            print(f"Error executing {script}: {e}")
            print(e.output)  # Print the error output if available
    else:
        print(f"Invalid choice: {choice}")

print("Selected scripts have been executed.")
