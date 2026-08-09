import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()

"""

┌──────────────────────────────────────────────────────────┐
│                   PRE-TRAINED BASE MODEL                 │
│  Trained on broad internet text (knows grammar, coding,  │
│  UI terminology, payment concepts, human language).      │
└────────────────────────────┬─────────────────────────────┘
                             │
                             ▼  [Transfer Learning / Fine-Tuning]
┌──────────────────────────────────────────────────────────┐
│                    FINE-TUNED MODEL                      │
│  Adapted to output strict 1-word internal routing tags   │
│  with 100% adherence and minimal token latency.          │
└──────────────────────────────────────────────────────────┘


OpenAI is winding down the fine-tuning platform and your organization is no longer able to 
create new fine-tuning training jobs. 
Learn more https://developers.openai.com/api/docs/deprecations#update-to-openais-self-serve-fine-tuning
"""

input_file = "transfer_learning_dataset.jsonl"

def upload_file():
    with open(input_file, "rb") as f:
        training_file = client.files.create(
            file=f,
            purpose="fine-tune"
        )
        return training_file


def run_transfer_learning():
    print("Uploading specialized dataset...")
    training_file = upload_file()
    print(f"File uploaded. File ID: {training_file.id}")
    print("\nInitiating Transfer Learning (Fine-Tuning job)...")
    # Transfer knowledge from base gpt-4o-mini to our specific classification task
    ft_job = client.fine_tuning.jobs.create(
        training_file=training_file.id,
        model="gpt-4o-mini"
    )
    print(f"Fine-Tuning Job Created ID: {ft_job.id}")

    # Monitor job status
    while True:
        job_status = client.fine_tuning.jobs.retrieve(ft_job.id)
        print(f"Current Job Status: {job_status.status}")

        if job_status.status == "succeeded":
            fine_tuned_model_id = job_status.fine_tuned_model
            print(f"\nTransfer Learning Complete! New Model ID: {fine_tuned_model_id}")
            break
        elif job_status.status in ["failed", "cancelled"]:
            raise Exception(f"Job failed with status: {job_status.status}")

        time.sleep(10)

    # Predict using the fine-tuned transfer model
    print("\nTesting target model inference:")
    test_input = "My credit card was billed twice after a failed checkout error."

    response = client.responses.create(
        model=fine_tuned_model_id,
        instructions="You are a customer feedback classifier.",
        input=test_input,
        temperature=0.0
    )
    print(f"Input: '{test_input}'")
    print(f"Predicted Tag: {getattr(response, 'output_text', '')}")


if __name__ == "__main__":
    run_transfer_learning()