FROM --platform=linux/amd64 python:3.10
WORKDIR /app
COPY process_pdfs.py .
RUN pip install pdfminer.six
CMD ["python", "process_pdfs.py"]
