# Personal archive (Root) - Read Me

The PineScript folder contains code that is used to analyze stock prices on the TradeView platform.

The Julia and NumPy folders include notebooks, respectively Pluto and Colab, for analyzing financial assets traded on the Brazilian stock exchange. The Python code is optimized by changing the logic of using for loops to array operations from the NumPy library. The `map` function applies the `calculate_values` function to each column of the `stockData` matrix, which is equivalent to the original for loop, but because the function is applied to each column simultaneously, the code is faster. Additionally, the NumPy functions from the Jax library are used, taking advantage of parallel processing in a GPU environment.

Technical specs and concept samples are included in the Projects' folder for new systems or new functionalities in present systems, covering data models, calculations logics and pseudocodes, workflows and prototyping validation criteria.

*Copyright: The code may be freely reproduced and fork/altered by the community. It is recommended that you give credit to the author.*

*Disclaimer: The author is not responsible for the results obtained from applying the code.*
