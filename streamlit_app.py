"""Image Downloader - Streamlit version (uses image_downloader.py).

Run:  streamlit run streamlit_app.py
"""
import io
import os
import tempfile
import zipfile
from urllib.error import URLError

import streamlit as st

import image_downloader

st.set_page_config(page_title="Image Downloader", layout="wide")
st.title("Image Downloader")
st.caption("Paste a direct image link or a web page link. Page links download every image on the page.")

url = st.text_input("Link", placeholder="https://example.com/page")

if st.button("Download images", type="primary"):
    if not url.strip():
        st.error("Enter a link first.")
    else:
        with tempfile.TemporaryDirectory() as folder:
            try:
                with st.spinner("Downloading..."):
                    paths = image_downloader.download_from_link(url.strip(), folder)
                    images = [(os.path.basename(p), open(p, "rb").read()) for p in paths]
            except (URLError, ValueError, OSError) as e:
                st.session_state.pop("images", None)
                st.error(str(e))
            else:
                st.session_state["images"] = images

images = st.session_state.get("images")
if images is not None:
    if not images:
        st.warning("No images found at that link.")
    else:
        st.success(f"{len(images)} image(s) downloaded.")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in images:
                z.writestr(name, data)
        st.download_button("Download all (.zip)", buf.getvalue(), file_name="images.zip",
                           mime="application/zip")
        cols = st.columns(4)
        for i, (name, data) in enumerate(images):
            with cols[i % 4]:
                if name.lower().endswith(".svg"):
                    st.caption(name)
                else:
                    st.image(data, caption=name, use_container_width=True)
                st.download_button("Download", data, file_name=name, key=f"dl_{i}")
