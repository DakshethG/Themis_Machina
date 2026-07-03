import datasets

def download_cuad():
    out_dir = "corpus/raw/datasets/cuad"
    print("Downloading CUAD dataset...")
    # using the explicit repository id to avoid HfUriError
    d = datasets.load_dataset("theatticusproject/cuad-qa", trust_remote_code=True)
    d.save_to_disk(out_dir)
    print("CUAD download complete.")

if __name__ == "__main__":
    download_cuad()
