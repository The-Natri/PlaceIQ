# Opens the report in Microsoft Word, updates every field (table of contents,
# page numbers), saves the .docx and exports a PDF next to it.
# Run from the repo root:  powershell -ExecutionPolicy Bypass -File docs/report/render_pdf.ps1
param([string]$Path = "docs/PlaceIQ_DA3_Report.docx")
$docx = (Resolve-Path $Path).Path
$pdf = [System.IO.Path]::ChangeExtension($docx, ".pdf")
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $doc = $word.Documents.Open($docx)
    $doc.Fields.Update() | Out-Null
    foreach ($toc in $doc.TablesOfContents) { $toc.Update() }
    # A second pass: the TOC's own page numbers can shift once it is filled in.
    $doc.Repaginate()
    foreach ($toc in $doc.TablesOfContents) { $toc.UpdatePageNumbers() }
    $doc.Save()
    $doc.ExportAsFixedFormat($pdf, 17)   # 17 = wdExportFormatPDF
    "pages: " + $doc.ComputeStatistics(2)  # 2 = wdStatisticPages
    $doc.Close()
    "wrote $pdf"
} finally {
    # Quit only if this Word instance has nothing else open: if the person
    # already had Word running, COM may hand back that same instance.
    if ($word.Documents.Count -eq 0) { $word.Quit() }
}
