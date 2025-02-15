import pandas as pd

def generate_binary_files(file_path, options):
    # Check if binary processing is enabled
    if not options.get("generate_binary_files", False):
        print("Binary file generation is disabled.")
        return None
    
    # Iterate through each binary file entry in config
    for file_name, file_config in options.get("binary_files", {}).items():
        
        # Load original fixture CSV file
        df = pd.read_csv(file_path)

        fixtures = file_config.get("fixtures", {})
        
        for team, binary_fix in fixtures.items():
            # Apply changes only to rows where the Team column matches the specified team
            team_mask = df["Team"] == team
            
            for new_gw, orig_gw in binary_fix.items():
                new_gw_pts_col = f"{new_gw}_Pts"
                new_gw_xmins_col = f"{new_gw}_xMins"
                orig_gw_pts_col = f"{orig_gw}_Pts"
                orig_gw_xmins_col = f"{orig_gw}_xMins"
                
                # Ensure relevant columns exist in the dataframe
                if all(col in df.columns for col in [new_gw_pts_col, new_gw_xmins_col, orig_gw_pts_col, orig_gw_xmins_col]):
                    # Convert columns to numeric values for the rows we are updating
                    df.loc[team_mask, new_gw_pts_col] = pd.to_numeric(df.loc[team_mask, new_gw_pts_col], errors='coerce')
                    df.loc[team_mask, new_gw_xmins_col] = pd.to_numeric(df.loc[team_mask, new_gw_xmins_col], errors='coerce')
                    df.loc[team_mask, orig_gw_pts_col] = pd.to_numeric(df.loc[team_mask, orig_gw_pts_col], errors='coerce')
                    df.loc[team_mask, orig_gw_xmins_col] = pd.to_numeric(df.loc[team_mask, orig_gw_xmins_col], errors='coerce')
                    
                    # Update key_Pts by adding key_value_Pts
                    df.loc[team_mask, new_gw_pts_col] += df.loc[team_mask, orig_gw_pts_col]
                    
                    # Average key_xMins and key_value_xMins
                    df.loc[team_mask, new_gw_xmins_col] = (
                        df.loc[team_mask, new_gw_xmins_col] + df.loc[team_mask, orig_gw_xmins_col]
                    ) / 2
                    
                    # Zero out key_value_Pts and key_value_xMins
                    df.loc[team_mask, [orig_gw_pts_col, orig_gw_xmins_col]] = 0
    
        # Save the updated CSV file
        df.to_csv("../data/" + file_name, index=False)
        print(f"Generated: {file_name}")