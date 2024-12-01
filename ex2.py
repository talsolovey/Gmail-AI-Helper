from gpt4all import GPT4All

# System prompt to define assistant behavior
system_prompt = "Cutting Knowledge Date: December 2023\n"
"You are a helpful assistant."

# Initialize the model
model = GPT4All("Llama-3.2-3B-Instruct-Q4_0.gguf")

# Create the prompt using the template
user_prompt = "Answer this prompt by saying 'Hello LLM'"

# Generate output using the system and user prompt template
output = model.generate(f"{system_prompt}\n{user_prompt}", max_tokens=5)

# Print the output
print(output)
