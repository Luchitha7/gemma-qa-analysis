import os

files_to_delete = [
    r'src\rag\knowledge_base.py',
    r'src\rag\rag.py',
    r'src\rag\rag_accuracy.py',
    r'src\rag\rag_compliance.py',
    r'src\services\qa_agent.py',
    r'src\services\qa_report.py',
    r'src\core\weights_config.py',
    r'src\core\report_pdf.py',
    r'src\api\job_queue.py',
    r'resources\prompts\scorecard_prompt.txt'
]

for f in files_to_delete:
    if os.path.exists(f):
        os.remove(f)
        print(f"Deleted {f}")
