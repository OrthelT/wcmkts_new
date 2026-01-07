# Migration Guide: Dynamic Ship Role Categorization

This update refactors how ships are categorized into roles (DPS, Logi, Links, Support) by moving hardcoded lists into a configuration file (`settings.toml`) and adding support for `fit_id`-based special cases (e.g., a ship that can be both DPS or Links depending on the fit).

## 1. Configuration Changes (`settings.toml`)

Add a `[ship_roles]` section to `settings.toml`. This allows role definitions to be managed without changing code.

**Key Feature:** `special_cases` dictionary mapping `Ship Name -> {Fit ID -> Role}`.

```toml:settings.toml
[ship_roles]
    dps = [
        'Hurricane', 'Hurricane Fleet Issue', 'Ferox', 'Zealot', 'Purifier', 'Tornado', 'Oracle',
        'Harbinger', 'Brutix', 'Myrmidon', 'Talos', 'Naga', 'Rokh',
        'Megathron', 'Hyperion', 'Dominix', 'Raven', 'Scorpion Navy Issue',
        'Raven Navy Issue', 'Typhoon', 'Tempest', 'Maelstrom', 'Abaddon',
        'Apocalypse', 'Armageddon', 'Rifter', 'Punisher', 'Merlin', 'Incursus',
        'Bellicose', 'Nightmare', 'Retribution', 'Vengeance', 'Exequror Navy Issue',
        'Hound', 'Nemesis', 'Manticore', 'Moa', 'Harpy', 'Tempest Fleet Issue', 'Cyclone Fleet Issue', 'Kikimora'
    ]
    
    logi = [
        'Osprey', 'Guardian', 'Basilisk', 'Scimitar', 'Oneiros',
        'Burst', 'Bantam', 'Inquisitor', 'Navitas', 'Zarmazd', 'Deacon', 'Thalia', 'Kirin'
    ]
    
    links = [
        'Claymore', 'Devoter', 'Drake', 'Cyclone', 'Sleipnir', 'Nighthawk',
        'Damnation', 'Astarte', 'Command Destroyer', 'Bifrost', 'Pontifex',
        'Stork', 'Magus', 'Hecate', 'Confessor', 'Jackdaw', 'Eos'
    ]

    support = [
        'Sabre', 'Stiletto', 'Malediction', 'Huginn', 'Rapier', 'Falcon',
        'Blackbird', 'Celestis', 'Arbitrator', 'Vigil',
        'Griffin', 'Maulus', 'Crucifier', 'Heretic', 'Flycatcher',
        'Eris', 'Dictor', 'Hictor', 'Broadsword', 'Phobos', 'Onyx',
        'Crow', 'Claw', 'Crusader', 'Taranis', 'Atron', 'Slasher',
        'Executioner', 'Condor', 'Svipul'
    ]

    # Special cases: Map Ship Name -> { Fit ID -> Role }
    # Note: TOML keys are strings, so fit IDs in the nested dict are strings or integers depending on parser, 
    # but the Python code should handle string conversion.
    special_cases = {Vulture={369='DPS', 475='Links'}, Deimos={202='DPS', 330='Support'}}
```

## 2. Code Changes (`pages/doctrine_report.py`)

### A. Update `categorize_ship_by_role`
Refactor this function to load from `settings.toml` and handle the `special_cases` logic.

```python
def categorize_ship_by_role(ship_name: str, fit_id: int) -> str:
    """Categorize ships by their primary fleet role."""
    # Convert fit_id to str to match TOML/JSON key format if necessary
    fit_id = str(fit_id) 
    
    import tomllib
    with open("settings.toml", "rb") as f:
        settings = tomllib.load(f)
        
    dps_ships = settings['ship_roles']['dps']
    logi_ships = settings['ship_roles']['logi']
    links_ships = settings['ship_roles']['links']
    support_ships = settings['ship_roles']['support']
    special_cases = settings['ship_roles']['special_cases']

    # Check special cases first (Ship Name + Fit ID lookup)
    if ship_name in special_cases and fit_id in special_cases[ship_name]:
        return special_cases[ship_name][fit_id]
    
    # Standard Category Checks
    elif ship_name in dps_ships:
        return "DPS"
    elif ship_name in logi_ships:
        return "Logi"
    elif ship_name in links_ships:
        return "Links"
    elif ship_name in support_ships:
        return "Support"
    else:
        # Fallback keyword matching (legacy support)
        if any(keyword in ship_name.lower() for keyword in ['hurricane', 'ferox', 'zealot', 'bellicose']):
            return "DPS"
        elif any(keyword in ship_name.lower() for keyword in ['osprey', 'guardian', 'basilisk']):
            return "Logi"
        elif any(keyword in ship_name.lower() for keyword in ['claymore', 'drake', 'cyclone']):
            return "Links"
        else:
            return "Support"
```

### B. Update `display_categorized_doctrine_data`
Update the DataFrame processing to use the new categorization logic and fix UI rendering issues for small tables.

**1. Apply the categorization:**
Replace the old `.apply()` logic with a lambda that passes *both* `ship_name` and `fit_id`.

```python
    # Create a proper copy of the DataFrame to avoid SettingWithCopyWarning
    selected_data_with_roles = selected_data.copy()
    
    # NEW: Pass both ship_name and fit_id to the categorization function
    selected_data_with_roles['role'] = selected_data_with_roles.apply(
        lambda row: categorize_ship_by_role(row['ship_name'], row['fit_id']), 
        axis=1
    )

    # REMOVED: Old hardcoded Vulture special case logic (now handled by categorize_ship_by_role)
    
    # Remove fit_id 474 using loc
    selected_data_with_roles = selected_data_with_roles.loc[selected_data_with_roles['fit_id'] != 474]
```

**2. Dynamic Dataframe Height:**
Add logic to calculate static height for small tables to prevent Streamlit from cutting off the bottom rows.

```python
            df['ship_target'] = df['ship_target'] * st.session_state.target_multiplier
            df['target_percentage'] = round(df['fits'] / df['ship_target'], 2)

            # NEW: Dynamic height calculation
            # 40px per row approximation + 50px header buffer
            static_height = len(df) * 40 + 50 if len(df) < 10 else 'auto'

            st.dataframe(
                df, 
                # ... column_config ...
                width='content',
                hide_index=True,
                height=static_height  # NEW: Apply the calculated height
            )
```

