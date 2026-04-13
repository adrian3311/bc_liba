import matplotlib.pyplot as plt

time = [1,2,3,4,5]
forecast = [10,12,14,13,15]
real = [9,11,13,12,14]

plt.plot(time, forecast, label="Predpoveď")
plt.plot(time, real, label="Realita")

plt.xlabel("čas")
plt.ylabel("teplota (°C)")
plt.legend()
plt.title("Porovnanie predpovede a reality")

plt.show()