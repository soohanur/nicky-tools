import UploadedFilesTable from "@/components/dashboard/UploadedFilesTable";

export const metadata = { title: "Uploaded Files" };

export default function FilesPage() {
  return (
    <section>
      <UploadedFilesTable />
    </section>
  );
}
