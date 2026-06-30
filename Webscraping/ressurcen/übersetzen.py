import json
import duden
import time, tqdm
from collections import deque
import multiprocessing

wort = "Donaudampfschifffahrtsgesellschaftskapitänmütze"  
utf8_zahlen = list(wort.encode('utf-8'))

print(utf8_zahlen) 
