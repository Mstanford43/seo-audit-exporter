import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="SEO Audit Tool", layout="wide")

st.title("🔍 SEO Audit Tool")
st.write("Upload a Screaming Frog CSV export to generate a full SEO audit report.")

# -----------------------------
# FILE UPLOAD
# -----------------------------
uploaded_file = st.file_uploader(
    "Upload Screaming Frog CSV",
    type=["csv"]
)

if uploaded_file:
    df = pd.read_csv(uploaded_file, encoding="utf-8-sig")

    # -----------------------------
    # SEGMENT CONTENT TYPES
    # -----------------------------
    html_pages = df[df["Content Type"].str.contains("text/html", na=False)]
    pdf_pages = df[df["Content Type"].str.contains("application/pdf", na=False)]

    indexable_html = html_pages[html_pages["Indexability"] == "Indexable"].copy()
    indexable_pdfs = pdf_pages[pdf_pages["Indexability"] == "Indexable"].copy()

    # -----------------------------
    # CLEAN COLUMNS FOR DUPLICATES
    # -----------------------------
    indexable_html["Title_1_clean"] = indexable_html["Title 1"].fillna("").str.strip().str.lower()
    indexable_html["H1_1_clean"] = indexable_html["H1-1"].fillna("").str.strip().str.lower()

    # -----------------------------
    # HELPERS
    # -----------------------------
    def get_duplicate_urls(df, column_clean, original_column):
        grouped = df.groupby(column_clean)["Address"].apply(list)
        duplicates = grouped[grouped.apply(len) > 1]
        exploded = duplicates.explode().reset_index(drop=True)
        return df[df["Address"].isin(exploded)][["Address", original_column]]

    def write_sheet(writer, data, columns, name, counts):
        if not data.empty:
            data[columns].to_excel(writer, sheet_name=name[:31], index=False, startrow=1)
            counts[name] = len(data)
        else:
            counts[name] = 0

    # -----------------------------
    # RUN AUDIT
    # -----------------------------
    output = io.BytesIO()
    sheet_counts = {}

    with pd.ExcelWriter(output, engine="openpyxl") as writer:

        # Missing Canonicals
        combined_missing_canonicals = pd.concat([
            indexable_html[indexable_html["Canonical Link Element 1"].isna()],
            indexable_pdfs[indexable_pdfs["Canonical Link Element 1"].isna()]
        ])
        write_sheet(writer, combined_missing_canonicals, ["Address"], "Missing Canonicals", sheet_counts)

        # Non-indexable Canonicals
        write_sheet(
            writer,
            html_pages[html_pages["Indexability"] == "Non-Indexable"],
            ["Address", "Indexability Status"],
            "Nonindexable URLs",
            sheet_counts
        )

        # Status Codes
        write_sheet(writer, html_pages[html_pages["Status Code"].between(300, 399)], ["Address", "Status Code"], "3XX URLs", sheet_counts)
        write_sheet(writer, html_pages[html_pages["Status Code"].between(400, 499)], ["Address", "Status Code"], "4XX URLs", sheet_counts)

        # Titles
        write_sheet(writer, indexable_html[indexable_html["Title 1"].isna() | (indexable_html["Title 1"].str.strip() == "")], ["Address"], "Missing Titles", sheet_counts)
        write_sheet(writer, indexable_html[indexable_html["Title 1 Length"] > 60], ["Address", "Title 1 Length"], "Titles Too Long", sheet_counts)
        write_sheet(writer, indexable_html[indexable_html["Title 1 Length"] < 30], ["Address", "Title 1 Length"], "Titles Too Short", sheet_counts)
        write_sheet(writer, get_duplicate_urls(indexable_html, "Title_1_clean", "Title 1"), ["Address", "Title 1"], "Duplicate Titles", sheet_counts)

        # H1s
        write_sheet(
            writer,
            indexable_html[
                (indexable_html["H1-1"].isna() | (indexable_html["H1-1"].str.strip() == "")) &
                (indexable_html["H1-2"].isna() | (indexable_html["H1-2"].str.strip() == ""))
            ],
            ["Address"],
            "Missing H1s",
            sheet_counts
        )

        write_sheet(writer, indexable_html[indexable_html["H1-1"].notna() & indexable_html["H1-2"].notna()], ["Address", "H1-1", "H1-2"], "Multiple H1s", sheet_counts)
        write_sheet(writer, get_duplicate_urls(indexable_html, "H1_1_clean", "H1-1"), ["Address", "H1-1"], "Duplicate H1s", sheet_counts)

        # Meta Descriptions
        write_sheet(writer, indexable_html[indexable_html["Meta Description 1"].isna()], ["Address"], "Missing Meta Descriptions", sheet_counts)
        write_sheet(writer, indexable_html[indexable_html["Meta Description 1 Length"] < 50], ["Address", "Meta Description 1 Length"], "Meta Too Short", sheet_counts)
        write_sheet(writer, indexable_html[indexable_html["Meta Description 1 Length"] > 160], ["Address", "Meta Description 1 Length"], "Meta Too Long", sheet_counts)
        write_sheet(writer, get_duplicate_urls(indexable_html, "Meta Description 1", "Meta Description 1"), ["Address", "Meta Description 1"], "Duplicate Meta Descriptions", sheet_counts)

        # Near Duplicates
        write_sheet(writer, indexable_html[indexable_html["No. Near Duplicates"] > 0], ["Address", "No. Near Duplicates"], "Near Duplicate Content", sheet_counts)

        # Orphan URLs
        write_sheet(writer, indexable_html[indexable_html["Inlinks"] == 0], ["Address"], "Orphan URLs", sheet_counts)

        # Dashboard
        dashboard = pd.DataFrame({
            "Issue": sheet_counts.keys(),
            "Count": sheet_counts.values()
        })
        dashboard.to_excel(writer, sheet_name="Summary Dashboard", index=False, startrow=1)

    st.success("✅ Audit complete!")
    st.dataframe(dashboard)

    st.download_button(
        label="📥 Download Excel Report",
        data=output.getvalue(),
        file_name="SEO_Issue_Output.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
