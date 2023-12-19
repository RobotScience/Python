#!/usr/bin/env python3
import argparse
import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument("-strat", "--Strategy", choices=['LevelEach', 'LevelDistributed'])
parser.add_argument("-fpw", "--FarmPerWave", choices=[1, 2], default=2)
parser.add_argument("-mfl", "--MaxFarmLevel", choices=[0, 1, 2, 3, 4, 5], default=5)
parser.add_argument("-mf", "--MaxFarms", choices=[1, 2, 3, 4, 5, 6, 7, 8], default=8)
parser.add_argument("-w", "--Waves", default=41)
args = parser.parse_args()

strategy = args.Strategy
farms_per_wave = args.FarmPerWave
mfl = args.MaxFarmLevel
mf = args.MaxFarms
waves = 41


def calculate_totals(dataframe, max_farms):
    
    # calculate total income
    total_income = 0
    for r in range(max_farms):
        r += 1
        fi = f'FARM-{str(r)}'
        total_income += dataframe.iloc[2][fi]
    
    # calculate total cost
    total_cost = 0
    for r in range(max_farms):
        r += 1
        fi = f'FARM-{str(r)}'
        total_cost += dataframe.iloc[1][fi]

    return {
        'TotalCost': total_cost,
        'TotalIncome': total_income
    }


def table_ize(df):
    if not isinstance(df, pd.DataFrame):
        return
    df_columns = df.columns.tolist()
    max_len_in_lst = lambda lst: len(sorted(lst, reverse=True, key=len)[0])
    align_center = lambda st, sz: "{0}{1}{0}".format(" "*(1+(sz-len(st))//2), st)[:sz] if len(st) < sz else st
    align_right = lambda st, sz: "{0}{1} ".format(" "*(sz-len(st)-1), st) if len(st) < sz else st
    max_col_len = max_len_in_lst(df_columns)
    max_val_len_for_col = dict([(col, max_len_in_lst(df.iloc[:,idx].astype('str'))) for idx, col in enumerate(df_columns)])
    col_sizes = dict([(col, 2 + max(max_val_len_for_col.get(col, 0), max_col_len)) for col in df_columns])
    build_hline = lambda row: '+'.join(['-' * col_sizes[col] for col in row]).join(['+', '+'])
    build_data = lambda row, align: "|".join([align(str(val), col_sizes[df_columns[idx]]) for idx, val in enumerate(row)]).join(['|', '|'])
    hline = build_hline(df_columns)
    out = [hline, build_data(df_columns, align_center), hline]
    for _, row in df.iterrows():
        out.append(build_data(row.tolist(), align_right))
    out.append(hline)
    return "\n".join(out)


def get_farm_values(l):
    p = {
            'level': {
                0: {
                    'cost': 250,
                    'income': 50
                },
                1: {
                    'cost': 200,
                    'income': 100
                },
                2: {
                    'cost': 550,
                    'income':250
                },
                3: {
                    'cost': 1000,
                    'income': 500
                },
                4: {
                    'cost': 2500,
                    'income': 750
                },
                5: {
                    'cost': 5000,
                    'income': 1500
                }
            }
        }
    return p['level'][l]


# create empty dict to be populated and set num farms to 0
farms = {}
num_farms = 0

if strategy == 'LevelDistributed':

    # cycle through each wave and calculate cost vs income
    for wave in range(waves):
        fpw = farms_per_wave
        # determine farms to add
        if num_farms < mf: # only add if we haven't reached max farms
            if (fpw + num_farms) > mf: # set farms per wave to 1 if we are going to go over max farms
                fpw = 1
            new_farms = fpw
        else:
            # no new farms will be added
            new_farms = 0
        for i in range(new_farms): # add new farms into dict
            # add count to num farms
            num_farms += 1
            # add new farm to dict
            farms[f'FARM-{str(num_farms)}'] = {
                'TotalCost': 0,
                'TotalIncome': 0,
                'Level': 0,
                'Capped': False
            }
        # iterate through
        for key in farms.keys():
            # assign level
            f = farms[key]
            level = f['Level']
            # get values from current level
            values = get_farm_values(level)
            # update dict with new values
            if level < mfl:
                update = {
                    'TotalCost': f['TotalCost'] + values['cost'],
                    'TotalIncome': f['TotalIncome'] + values['income'],
                    'Level': level + 1,
                    'Capped': False
                }
            elif level == mfl and not f['Capped']:
                update = {
                    'TotalCost': f['TotalCost'] + values['cost'],
                    'TotalIncome': f['TotalIncome'] + values['income'],
                    'Level': level,
                    'Capped': True
                }
            elif level == mfl and f['Capped']:
                update = {
                    'TotalCost': f['TotalCost'],
                    'TotalIncome': (f['TotalIncome'] + values['income']),
                    'Level': level
                }
            # update the dict with the new values
            farms[key].update(update)

if strategy == 'LevelEach':

    max_range = mfl - 1
    # cycle through each wave and calculate cost vs income
    for wave in range(waves):
        if num_farms == 0:
            num_farms += 1
            farms[f'FARM-{str(num_farms)}'] = {
                'TotalCost': 0,
                'TotalIncome': 0,
                'Level': 0,
                'Capped': False
            }
        if num_farms > 0:
            for key in list(farms):
                f = farms[key]
                level = f['Level']
                values = get_farm_values(level)
                if level in range(0, max_range):
                    for r2 in range(0, 2):
                        update = {
                            'TotalCost': f['TotalCost'] + values['cost'],
                            'TotalIncome': f['TotalIncome'] + values['income'],
                            'Level': level + 1,
                            'Capped': False
                        }
                        farms[key].update(update)
                        level += 1
                        values = get_farm_values(level)
                elif level == (mfl - 1):
                    update = {
                        'TotalCost': f['TotalCost'] + values['cost'],
                        'TotalIncome': f['TotalIncome'] + values['income'],
                        'Level': level + 1,
                        'Capped': False
                    }
                    farms[key].update(update)
                elif level == mfl and not f['Capped']:
                    # update and cap the current farm
                    update = {
                        'TotalCost': f['TotalCost'] + values['cost'],
                        'TotalIncome': f['TotalIncome'] + values['income'],
                        'Level': level,
                        'Capped': True
                    }
                    farms[key].update(update)
                    # add in a new farm
                    if num_farms < mf:
                        num_farms += 1
                        farms[f'FARM-{str(num_farms)}'] = {
                            'TotalCost': 250,
                            'TotalIncome': 200,
                            'Level': 0,
                            'Capped': False
                        }
                elif level == mfl and f['Capped']:
                    update = {
                        'TotalCost': f['TotalCost'],
                        'TotalIncome': (f['TotalIncome'] + values['income']),
                        'Level': level
                    }
                    farms[key].update(update)

# drop capped row and display the dataframe
df = pd.DataFrame(farms).sort_index().reset_index()
df.drop(0, inplace=True)
print("Farms income and cost report:\n\n")
print(table_ize(df))

# calculate cost and income
money = calculate_totals(df, mf)

print(f"\nTOTAL INCOME ====> {money['TotalIncome']}")
print(f"TOTAL COST   ====> {money['TotalCost']}\n")
print(f"NET INCOME   ====> {money['TotalIncome'] - money['TotalCost']}")
