import pypsa

import pandas as pd

import numpy as np
# NB: this example will use units of kW and kWh, unlike the PyPSA defaults
import matplotlib.pyplot as plt


half_hour_data=pd.read_csv('home_e_and_t_load.csv')
# data from https://octopus.energy/blog/domestic-energy-usage-patterns-during-social-distancing/

heat=True
boiler=False
HP=True

solar=True

E_storage=True
T_storage=True



day_E_load=[]
day_T_load=[]
day_solar=[]

# demand_t=(half_hour_data["Demand"])
snapshots = range(0,48)#len(half_hour_data["pre_e"]))
idx=0

con='post'

for i in range(len(snapshots)):
    day_E_load.append(half_hour_data[con+"_e"][i+idx])
    day_T_load.append(half_hour_data[con+"_t"][i+idx])
    day_solar.append(half_hour_data["solar"][i+idx]/1e3)


# use 24 hour period for consideration
index =snapshots

# consumption pattern of BEV
bev_usage = pd.Series(day_E_load,index)

# solar PV panel generation per unit of capacity
pv_pu = pd.Series(day_solar,index)

# availability of charging - i.e. only when parked at office
charger_p_max_pu = pd.Series(1.,index=index)


network = pypsa.Network()

network.set_snapshots(index)

network.add("Bus",
            "place of work",
            carrier="AC")
if E_storage:
    network.add("Bus",
            "battery",
            carrier="Li-ion")
if solar:
    network.add("Generator",
            "PV panel",
            bus="place of work",
            p_nom_extendable=True,
            p_max_pu=pv_pu,
            p_nom_min=0,
            capital_cost=200.,marginal_cost=0)

network.add("Generator",
            "gen",
            bus="place of work",
            p_nom_extendable=True,
            capital_cost=1000, marginal_cost=.3)

network.add("Load",
            "e_load",
            bus="place of work",
            p_set=bev_usage)
if E_storage:
    network.add("Link",
            "charger",
            bus0="place of work",
            bus1="battery",
            p_nom=120,  #super-charger with 120 kW
            p_max_pu=charger_p_max_pu,
            efficiency=0.9)

    network.add("Link",
            "discharger",
            bus0="battery",
            bus1="place of work",
            p_nom=120,  #super-charger with 120 kW
            p_max_pu=charger_p_max_pu,
            efficiency=0.9)

if E_storage:
    network.add("Store",
            "battery storage",
            bus="battery",
            e_cyclic=True,
            e_nom=5, e_nom_extenable=True)


if heat:
    network.add("Bus",
                "heat",
                carrier="heat")

    network.add("Carrier",
                "heat")

    network.add("Load",
                "t_load",
                bus="heat",
                carrier="heat",
                p_set=day_T_load)

    if T_storage:

        network.add("Store",
                "water tank",
                bus="heat",
                carrier="heat",
                e_cyclic=True,
                e_nom_extendable=True,
                e_nom_max=.7 * 1e3 * 70 * 4200 / 3.6e3)

if boiler:
    network.add("Bus",
                "gas",
                carrier="gas")
    network.add("Carrier",
                "gas",
                co2_emissions=0.2)

    network.add("Generator",
                "gas_gen",
                bus="gas",
                carrier="gas",
                efficiency=1,
                p_nom_extendable=True)


    network.add("Link",
                "boiler",
                bus0="gas",
                bus1="heat",
                efficiency=0.9,
                marginal_cost=1,
                capital_cost=1,
                p_nom_extendable=True)

if HP:
    network.add("Link",
                "HP",
                bus0="place of work",
                bus1="heat",
                efficiency=3,
                p_nom_extendable=True)



network.lopf(network.snapshots)
print("Objective:",network.objective)
if solar:
    print("Pannel size [kW]:",network.generators.p_nom_opt["PV panel"])
if E_storage:
    print("Batt size [kWh]:",network.stores.e_nom_opt)

snapshots=np.array(snapshots)/48

fig, ax= plt.subplots()
# ax.plot(snapshots,network.generators.p_nom_opt["PV panel"]*pv_pu,label='solar0')
ax.plot(snapshots, network.loads_t.p['e_load'],label='load')
ax.plot(snapshots, network.generators_t.p['gen'], label='power from grid')

if solar:
    ax.plot(snapshots, network.generators_t.p["PV panel"], label='solar')

if E_storage:
    ax.plot(snapshots, network.stores_t.p['battery storage'], label='batt')


ax.set_xlabel('time in a week')
ax.set_ylabel('power [MW]')
ax.set_title('Power')


if heat and boiler:
    fig2, ax2=plt.subplots()
    # ax.plot(snapshots,network.links_t["p0"],label='chp_p')
    # ax2.plot(snapshots, network.generators_t.p['heat gen'], label='heat from grid')
    ax2.plot(snapshots, np.array(network.loads_t.p["t_load"]), label='heat_load')
    ax2.plot(snapshots,-network.links_t.p1['boiler'],label='power from boiler')

    ax2.set_xlabel('time in a week')
    ax2.set_ylabel('heat power [kW]')
    ax2.set_title('Heat')




if heat and HP:

    ax.plot(snapshots, network.links_t.p0['HP'], label='HP_E')
    fig2, ax2 = plt.subplots()
    # ax.plot(snapshots,network.links_t["p0"],label='chp_p')
    # ax2.plot(snapshots, network.generators_t.p['heat gen'], label='heat from grid')
    ax2.plot(snapshots, np.array(network.loads_t.p["t_load"]), label='heat_load')
    ax2.plot(snapshots, -network.links_t.p1['HP'], label='HP_T')

    ax2.set_xlabel('time in a week')
    ax2.set_ylabel('heat power [kW]')
    ax2.set_title('Heat')
    if T_storage:
        ax2.plot(snapshots, -network.stores_t.p['water tank'], label='thermal store')

ax2.legend(loc='upper right')
ax.legend()

plt.show()

if solar==False:
    results=pd.concat([network.loads_t.p["e_load"], network.loads_t.p["t_load"]], axis=1, sort=False)
    results.to_csv("no_solar_results.csv")
else:
    results = pd.concat([network.loads_t.p["e_load"], network.loads_t.p["t_load"], network.generators_t.p["PV panel"], network.stores_t.p['battery storage'],
                         network.stores_t.p['water tank'], network.links_t.p0['HP'],-network.links_t.p1['HP']], axis=1, sort=False)
    results.to_csv("solar_results.csv")


print(np.sum(np.array()))







