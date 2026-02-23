import { AddSchoolForm } from "./add-school-form";

export const metadata = {
  title: "Add School",
};

export default function AddSchoolPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Add School</h1>
        <p className="text-muted-foreground">
          Add a new school to your chain. You can configure details and branding after creation.
        </p>
      </div>
      <AddSchoolForm />
    </div>
  );
}
