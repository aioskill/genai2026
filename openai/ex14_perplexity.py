import os
import openai
import math
from dotenv import load_dotenv

load_dotenv()

# Set the model name.
OPENAI_MODEL = os.getenv("OPENAI_MODEL")

# Define the prompt you want to send to the model.
# prompt = """Once upon a time in a land far far away"""
# prompt = """What is the capital of France? Answer in one word."""

# prompt = """
# Write a 100-word paragraph on the benefits of yoga for mental health.
# Focus on the calming effect of yoga on the nervous system, stress reduction,
# and improved concentration and mental clarity. Avoid talking about the physical aspects of yoga,
# and focus only on the aspects related to mental health.
# """ # Perplexity Score : 1.2453

# prompt = """
# Compose a 100-word essay about how yoga positively impacts mental well-being.
# Highlight the calming influence on the mind, its role in reducing stress,
# and how it sharpens focus and clarity.
# """ # Perplexity Score : 1.3597

# prompt = "Generate a 2-day itinerary for a cultural trip to Rome." # Perplexity Score : 1.2245
prompt = "Craft a detailed 2-day cultural journey plan for visiting Rome's historic landmarks and museums." # Perplexity Score : 1.2217, 1.2856

client = openai.OpenAI()


def calculate_perplexity_and_confidence(logprobs_content):
    """
    Calculates Perplexity and Average Confidence from response.choices[0].logprobs.content.

    Perplexity = exp(-mean(logprobs))
    """
    if not logprobs_content:
        return {"perplexity": None, "avg_confidence_pct": None, "total_tokens": 0}

    # Extract logprob floats for each generated token
    logprob_values = [token_info.logprob for token_info in logprobs_content]

    total_tokens = len(logprob_values)

    # 1. Compute average log probability: (1 / N) * sum(logprobs)
    mean_logprob = sum(logprob_values) / total_tokens

    # 2. Compute Perplexity: exp(-mean_logprob)
    perplexity = math.exp(-mean_logprob)

    # 3. Compute Average Probability / Confidence percentage
    avg_confidence_pct = math.exp(mean_logprob) * 100

    return {
        "perplexity": round(perplexity, 4),
        "avg_confidence_pct": round(avg_confidence_pct, 2),
        "total_tokens": total_tokens,
        "mean_logprob": round(mean_logprob, 4)
    }

# Send the prompt to the OpenAI API and get the response.
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}],
    logprobs=True,
    top_logprobs=3,
    temperature=0.0
)

# Extract logprobs content array
logprobs_content = response.choices[0].logprobs.content

# Calculate perplexity
metrics = calculate_perplexity_and_confidence(logprobs_content)

print(f"Generated Output : {repr(response.choices[0].message.content)}")
print(f"Total Tokens     : {metrics['total_tokens']}")
print(f"Mean Logprob     : {metrics['mean_logprob']}")
print(f"Perplexity Score : {metrics['perplexity']}")
print(f"Avg Confidence   : {metrics['avg_confidence_pct']}%")