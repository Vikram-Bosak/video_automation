# Google Vids Auto-Generator

This repository contains a Playwright automation script to generate and download videos from Google Vids automatically using prompts from a CSV file.

## Open in Google Colab

Click the badge below to run this project directly in Google Colab:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/vikramkumarbosak/video_automation/blob/main/automation_colab.ipynb)

## Instructions

1. Upload your `prompts.csv` file.
2. Run the notebook cells.
3. **IMPORTANT:** The script gives you 60 seconds to manually log in to your Google Account when the browser opens. This is required because Google Vids is behind Google authentication.
4. After logging in, the script will automatically type the prompts, generate the videos, and download them.

## Files

- `main.py`: The main Playwright automation script.
- `prompts.csv`: Sample input file.
- `automation_colab.ipynb`: Jupyter Notebook for Colab integration.
- `requirements.txt`: Python dependencies.
