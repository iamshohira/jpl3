from deco_figure import DecoFigure
import numpy as np

fig = DecoFigure()

ax = fig.subplots(2,2,sharex=True)
ax[0,0].plot([1,2,3],[2,3,4])
ax[0,1].plot([1,2,3],[2,3,4], color='red')
ax[1,0].plot([1,2,3],[2,3,4], label='line1')
ax[1,1].plot([1,2,3],[2,3,4], linestyle='dashed', label='line2')
ax[0,0].plot(np.linspace(0,100,10000), np.linspace(0,100,10000), marker='o', label='line3')