import pandas as pd
import os
import glob

gw = int(input("What GW are you assessing? "))
situation = input("Is this a wildcard? (y/n) ")
print()

directory = '../data/results/'
no_plans = len(os.listdir(directory))

if situation == "N" or situation == "n": 

    buys = []
    sells = []

    for filename in os.listdir(directory):
        f = os.path.join(directory, filename)
        if os.path.isfile(f):
            plan = pd.read_csv(f)
            if plan[(plan['week']==gw) & (plan['transfer_in']==1)]['name'].to_list() == []:
                buys += ['No transfer']
                sells += ['No transfer']
            else:
                buy_list = plan[(plan['week']==gw) & (plan['transfer_in']==1)]['name'].to_list()
                buy = ', '.join(buy_list)
                buys.append(buy)

                sell_list = plan[(plan['week']==gw) & (plan['transfer_out']==1)]['name'].to_list()
                sell = ', '.join(sell_list)
                sells.append(sell)

    buy_sum = pd.DataFrame(buys, columns=['player']).value_counts().reset_index(name='PSB')
    sell_sum = pd.DataFrame(sells, columns=['player']).value_counts().reset_index(name='PSB')

    buy_sum['PSB'] = ["{:.0%}".format(buy_sum['PSB'][x]/no_plans) for x in range(buy_sum.shape[0])]
    sell_sum['PSB'] = ["{:.0%}".format(sell_sum['PSB'][x]/no_plans) for x in range(sell_sum.shape[0])]

    print('Buy:')
    print('\n'.join(buy_sum.to_string(index = False).split('\n')[1:]))
    print()
    print('Sell:')
    print('\n'.join(sell_sum.to_string(index = False).split('\n')[1:]))
    print()

elif situation == "Y" or situation == "y":

    goalkeepers = []
    defenders = []
    midfielders = []
    forwards = []

    for filename in os.listdir(directory):
        f = os.path.join(directory, filename)
        if os.path.isfile(f):
            plan = pd.read_csv(f)
            goalkeepers += plan[(plan['week']==gw) & (plan['pos']=='GKP') & (plan['transfer_out']!=1)]['name'].to_list()
            defenders += plan[(plan['week']==gw) & (plan['pos']=='DEF') & (plan['transfer_out']!=1)]['name'].to_list()
            midfielders += plan[(plan['week']==gw) & (plan['pos']=='MID') & (plan['transfer_out']!=1)]['name'].to_list()
            forwards += plan[(plan['week']==gw) & (plan['pos']=='FWD') & (plan['transfer_out']!=1)]['name'].to_list()

    keepers = pd.DataFrame(goalkeepers, columns=['player']).value_counts().reset_index(name='PSB')
    defs = pd.DataFrame(defenders, columns=['player']).value_counts().reset_index(name='PSB')
    mids = pd.DataFrame(midfielders, columns=['player']).value_counts().reset_index(name='PSB')
    fwds = pd.DataFrame(forwards, columns=['player']).value_counts().reset_index(name='PSB')

    keepers['PSB'] = ["{:.0%}".format(keepers['PSB'][x]/no_plans) for x in range(keepers.shape[0])]
    defs['PSB'] = ["{:.0%}".format(defs['PSB'][x]/no_plans) for x in range(defs.shape[0])]
    mids['PSB'] = ["{:.0%}".format(mids['PSB'][x]/no_plans) for x in range(mids.shape[0])]
    fwds['PSB'] = ["{:.0%}".format(fwds['PSB'][x]/no_plans) for x in range(fwds.shape[0])]

    print('Goalkeepers:')
    print('\n'.join(keepers.to_string(index = False).split('\n')[1:]))
    print()
    print('Defenders:')
    print('\n'.join(defs.to_string(index = False).split('\n')[1:]))
    print()
    print('Midfielders:')
    print('\n'.join(mids.to_string(index = False).split('\n')[1:]))
    print()
    print('Forwards:')
    print('\n'.join(fwds.to_string(index = False).split('\n')[1:]))

else:
    print("Invalid input, please enter 'y' for a wildcard or 'n' for a regular transfer plan.")
