FROM --platform=linux/amd64 python:3.10
WORKDIR /app
COPY process_pdfs.py .
CMD ["python", "process_pdfs.py"]
