import pandas as pd
import os
import glob

gw = int(input("What is the current GW? "))
print()

directory = '../data/results/'
no_plans = len(os.listdir(directory))
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

