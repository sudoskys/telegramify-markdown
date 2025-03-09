
import matplotlib.pyplot as plt

from matplotlib import rcParams
rcParams['text.usetex'] = True

txte = r"The \emph{characteristic polynomial} $\chi(\lambda)$ of the $3 \times 3$~matrix \\ $\left( \begin{array}{ccc} a & b & c \\ d & e & f \\g & h & i \end{array} \right) $ \\is given by the formula\\ $ \chi(\lambda) = \left| \begin{array}{ccc} \lambda - a & -b & -c \\ -d & \lambda - e & -f \\ -g & -h & \lambda - i \end{array} \right|. $"


plt.text(0.0, 0.0, txte, fontsize=14)
ax = plt.gca()
ax.axes.get_xaxis().set_visible(False)
ax.axes.get_yaxis().set_visible(False)

plt.show()