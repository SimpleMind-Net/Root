# GPTalk: A pseudo-language interpreter at a prompt

GPT is a very useful and versatile **tool**. I started to use it daily, from simple questions (the kind I used to search in Google) to more complex analyzes using information resulting from a web search. I usually get the answer I want, but I have to put some time into an incremental process of refining the prompts.

GPTalk is a pseudo-language specification designed to **gain more control and assertiveness in GPT responses**. This is accomplished by writing a functionally structured prompt using natural language instructions *that accept GPTalk variables, operators, and functions*.

To use it, simply paste the entire content of the text file "GPTalk prompt" and send it at the first prompt of a conversation. The chatbot will reply that it is a GPTalk interpreter and ask you to enter your code. At the next prompt(s) write your instructions using the "language" specified in the first prompt. Through the prompts, you can enter code as you would into cells in a Jupyter notebook. GPT keeps data stored in variables in memory, for example. The coding is flexible: if the instructions use commands that are incomplete or slightly different from the specified one, GPT "understands" what you want and "guesses" what the correct instruction would be ⁽¹⁾.

I verified that it also runs flawlessly on the LLM Vicuna-13B chatbot created by researchers at UC Berkeley, CMU, Stanford, and UC San Diego.

The biggest difficulty in development was writing a prompt concise enough to meet the prompt's 2000 character limitation and still get the desired interpreter behavior of the GPTalk instructions by the chatbot ⁽²⁾.
I consider the current version of GPTalk ⁽³⁾, very preliminary, done in a few hours, but it meets my objective and I will use it: In the first tests I did, I successfully obtained, in the first prompts, an analysis of financial statements of some companies! Results are best at GPT-4.

* ###### (1) Even though GPT follows as specified. For example, in version 0.0.1 I used curly braces to identify variables within the natural language text of a instruction, and I changed it to a dollar sign preceding the variable name in version 0.0.2. In the test I forgot about this change and put the variables between curly braces. GPT did not understand. I changed it to dollar sign, it ran perfectly.
* ###### (2) I asked the GPT itself for help with this, without success. The answer always came back in the direction of guiding me on how I could write more efficient queries. At one point he initiated the response stating that it was an LLM designed for interactive dialogue and using it as an interpreter could limit that interaction.
* ###### (3) I didn't make up this name, "GPTalk" was suggested by GPT itself!*
