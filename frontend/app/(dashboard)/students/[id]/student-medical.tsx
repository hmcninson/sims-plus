"use client";

import { useState } from "react";
import {
  Heart,
  Droplet,
  AlertTriangle,
  AlertCircle,
  Pill,
  Phone,
  Building,
  UserRound,
  Plus,
  Trash2,
  Edit,
  Loader2,
  Save,
  Stethoscope,
} from "lucide-react";
import { toast } from "sonner";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";

import { updateStudent } from "@/actions/students.action";
import type { StructuredMedical, StudentWithGuardians } from "@/types";

const SEVERITY_OPTIONS = ["mild", "moderate", "severe"] as const;
const BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"] as const;

const conditionSchema = z.object({
  name: z.string().min(1, "Condition name is required"),
  severity: z.string().optional(),
  diagnosed_date: z.string().optional(),
  notes: z.string().optional(),
});

const allergySchema = z.object({
  name: z.string().min(1, "Allergy name is required"),
  severity: z.string().optional(),
  reaction: z.string().optional(),
});

const medicationSchema = z.object({
  name: z.string().min(1, "Medication name is required"),
  dosage: z.string().optional(),
  frequency: z.string().optional(),
  prescriber: z.string().optional(),
});

const medicalFormSchema = z.object({
  conditions: z.array(conditionSchema),
  allergies: z.array(allergySchema),
  medications: z.array(medicationSchema),
  emergency_protocol: z.string().optional(),
  doctor_name: z.string().optional(),
  doctor_phone: z.string().optional(),
  hospital: z.string().optional(),
  blood_group: z.string().optional(),
});

type MedicalFormValues = z.infer<typeof medicalFormSchema>;

function getSeverityColor(severity?: string): string {
  switch (severity) {
    case "mild":
      return "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400";
    case "moderate":
      return "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400";
    case "severe":
      return "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400";
    default:
      return "bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400";
  }
}

interface StudentMedicalProps {
  student: StudentWithGuardians;
  onUpdate: () => void;
}

export function StudentMedical({ student, onUpdate }: StudentMedicalProps) {
  const [isEditing, setIsEditing] = useState(false);

  const structuredMedical = student.structured_medical;
  const hasStructuredData = structuredMedical &&
    ((structuredMedical.conditions?.length ?? 0) > 0 ||
      (structuredMedical.allergies?.length ?? 0) > 0 ||
      (structuredMedical.medications?.length ?? 0) > 0 ||
      structuredMedical.doctor_name ||
      structuredMedical.emergency_protocol);

  // Has any medical data (legacy text-based or structured)
  const hasAnyData = student.blood_group ||
    student.medical_conditions ||
    student.allergies ||
    hasStructuredData;

  const form = useForm<MedicalFormValues>({
    resolver: zodResolver(medicalFormSchema),
    defaultValues: {
      conditions: structuredMedical?.conditions || [],
      allergies: structuredMedical?.allergies || [],
      medications: structuredMedical?.medications || [],
      emergency_protocol: structuredMedical?.emergency_protocol || "",
      doctor_name: structuredMedical?.doctor_name || "",
      doctor_phone: structuredMedical?.doctor_phone || "",
      hospital: structuredMedical?.hospital || "",
      blood_group: structuredMedical?.blood_group || student.blood_group || "",
    },
  });

  const conditionsField = useFieldArray({ control: form.control, name: "conditions" });
  const allergiesField = useFieldArray({ control: form.control, name: "allergies" });
  const medicationsField = useFieldArray({ control: form.control, name: "medications" });

  const handleSave = async (values: MedicalFormValues) => {
    const structuredData: StructuredMedical = {
      conditions: values.conditions,
      allergies: values.allergies,
      medications: values.medications,
      emergency_protocol: values.emergency_protocol || undefined,
      doctor_name: values.doctor_name || undefined,
      doctor_phone: values.doctor_phone || undefined,
      hospital: values.hospital || undefined,
      blood_group: values.blood_group || undefined,
    };

    const result = await updateStudent(student.id, {
      structured_medical: structuredData,
      blood_group: values.blood_group || undefined,
    });

    if (result.success) {
      toast.success("Medical information updated");
      setIsEditing(false);
      onUpdate();
    } else {
      toast.error(result.error || "Failed to update medical information");
    }
  };

  const handleStartEdit = () => {
    form.reset({
      conditions: structuredMedical?.conditions || [],
      allergies: structuredMedical?.allergies || [],
      medications: structuredMedical?.medications || [],
      emergency_protocol: structuredMedical?.emergency_protocol || "",
      doctor_name: structuredMedical?.doctor_name || "",
      doctor_phone: structuredMedical?.doctor_phone || "",
      hospital: structuredMedical?.hospital || "",
      blood_group: structuredMedical?.blood_group || student.blood_group || "",
    });
    setIsEditing(true);
  };

  if (isEditing) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Heart className="h-4 w-4" />
            Edit Medical Information
          </CardTitle>
          <CardDescription>
            Update health records, conditions, allergies, and medications.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(handleSave)} className="space-y-6">
              {/* Blood Group */}
              <FormField
                control={form.control}
                name="blood_group"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Blood Group</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value || ""}>
                      <FormControl>
                        <SelectTrigger className="w-full sm:w-[200px]">
                          <SelectValue placeholder="Select blood group" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="unknown">Unknown</SelectItem>
                        {BLOOD_GROUPS.map((bg) => (
                          <SelectItem key={bg} value={bg}>{bg}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <Separator />

              {/* Conditions */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-medium flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-yellow-500" />
                    Medical Conditions
                  </h4>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => conditionsField.append({ name: "", severity: "", diagnosed_date: "", notes: "" })}
                  >
                    <Plus className="h-3 w-3 mr-1" />
                    Add
                  </Button>
                </div>
                {conditionsField.fields.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No conditions recorded.</p>
                ) : (
                  <div className="space-y-3">
                    {conditionsField.fields.map((field, index) => (
                      <div key={field.id} className="grid grid-cols-1 md:grid-cols-2 gap-3 p-3 rounded-lg border">
                        <FormField
                          control={form.control}
                          name={`conditions.${index}.name`}
                          render={({ field: f }) => (
                            <FormItem>
                              <FormLabel className="text-xs">Condition</FormLabel>
                              <FormControl>
                                <Input placeholder="e.g. Asthma" {...f} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <FormField
                          control={form.control}
                          name={`conditions.${index}.severity`}
                          render={({ field: f }) => (
                            <FormItem>
                              <FormLabel className="text-xs">Severity</FormLabel>
                              <Select onValueChange={f.onChange} value={f.value || ""}>
                                <FormControl>
                                  <SelectTrigger>
                                    <SelectValue placeholder="Select severity" />
                                  </SelectTrigger>
                                </FormControl>
                                <SelectContent>
                                  {SEVERITY_OPTIONS.map((s) => (
                                    <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <FormField
                          control={form.control}
                          name={`conditions.${index}.diagnosed_date`}
                          render={({ field: f }) => (
                            <FormItem>
                              <FormLabel className="text-xs">Diagnosed Date</FormLabel>
                              <FormControl>
                                <Input placeholder="DD/MM/YYYY" {...f} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <div className="flex items-end gap-2">
                          <FormField
                            control={form.control}
                            name={`conditions.${index}.notes`}
                            render={({ field: f }) => (
                              <FormItem className="flex-1">
                                <FormLabel className="text-xs">Notes</FormLabel>
                                <FormControl>
                                  <Input placeholder="Additional notes" {...f} />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-9 w-9 shrink-0 text-muted-foreground hover:text-destructive"
                            onClick={() => conditionsField.remove(index)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <Separator />

              {/* Allergies */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-medium flex items-center gap-2">
                    <AlertCircle className="h-4 w-4 text-orange-500" />
                    Allergies
                  </h4>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => allergiesField.append({ name: "", severity: "", reaction: "" })}
                  >
                    <Plus className="h-3 w-3 mr-1" />
                    Add
                  </Button>
                </div>
                {allergiesField.fields.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No allergies recorded.</p>
                ) : (
                  <div className="space-y-3">
                    {allergiesField.fields.map((field, index) => (
                      <div key={field.id} className="flex items-start gap-3 p-3 rounded-lg border">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 flex-1">
                          <FormField
                            control={form.control}
                            name={`allergies.${index}.name`}
                            render={({ field: f }) => (
                              <FormItem>
                                <FormLabel className="text-xs">Allergen</FormLabel>
                                <FormControl>
                                  <Input placeholder="e.g. Peanuts" {...f} />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                          <FormField
                            control={form.control}
                            name={`allergies.${index}.severity`}
                            render={({ field: f }) => (
                              <FormItem>
                                <FormLabel className="text-xs">Severity</FormLabel>
                                <Select onValueChange={f.onChange} value={f.value || ""}>
                                  <FormControl>
                                    <SelectTrigger>
                                      <SelectValue placeholder="Select" />
                                    </SelectTrigger>
                                  </FormControl>
                                  <SelectContent>
                                    {SEVERITY_OPTIONS.map((s) => (
                                      <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                          <FormField
                            control={form.control}
                            name={`allergies.${index}.reaction`}
                            render={({ field: f }) => (
                              <FormItem>
                                <FormLabel className="text-xs">Reaction</FormLabel>
                                <FormControl>
                                  <Input placeholder="e.g. Rash, swelling" {...f} />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-9 w-9 shrink-0 mt-6 text-muted-foreground hover:text-destructive"
                          onClick={() => allergiesField.remove(index)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <Separator />

              {/* Medications */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-medium flex items-center gap-2">
                    <Pill className="h-4 w-4 text-blue-500" />
                    Current Medications
                  </h4>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => medicationsField.append({ name: "", dosage: "", frequency: "", prescriber: "" })}
                  >
                    <Plus className="h-3 w-3 mr-1" />
                    Add
                  </Button>
                </div>
                {medicationsField.fields.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No medications recorded.</p>
                ) : (
                  <div className="space-y-3">
                    {medicationsField.fields.map((field, index) => (
                      <div key={field.id} className="flex items-start gap-3 p-3 rounded-lg border">
                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 flex-1">
                          <FormField
                            control={form.control}
                            name={`medications.${index}.name`}
                            render={({ field: f }) => (
                              <FormItem>
                                <FormLabel className="text-xs">Medication</FormLabel>
                                <FormControl>
                                  <Input placeholder="Name" {...f} />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                          <FormField
                            control={form.control}
                            name={`medications.${index}.dosage`}
                            render={({ field: f }) => (
                              <FormItem>
                                <FormLabel className="text-xs">Dosage</FormLabel>
                                <FormControl>
                                  <Input placeholder="e.g. 5mg" {...f} />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                          <FormField
                            control={form.control}
                            name={`medications.${index}.frequency`}
                            render={({ field: f }) => (
                              <FormItem>
                                <FormLabel className="text-xs">Frequency</FormLabel>
                                <FormControl>
                                  <Input placeholder="e.g. Twice daily" {...f} />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                          <FormField
                            control={form.control}
                            name={`medications.${index}.prescriber`}
                            render={({ field: f }) => (
                              <FormItem>
                                <FormLabel className="text-xs">Prescriber</FormLabel>
                                <FormControl>
                                  <Input placeholder="Doctor name" {...f} />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-9 w-9 shrink-0 mt-6 text-muted-foreground hover:text-destructive"
                          onClick={() => medicationsField.remove(index)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <Separator />

              {/* Emergency Protocol */}
              <FormField
                control={form.control}
                name="emergency_protocol"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Emergency Protocol</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Describe emergency procedures for this student's conditions..."
                        rows={3}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Doctor Information */}
              <div className="space-y-3">
                <h4 className="font-medium flex items-center gap-2">
                  <Stethoscope className="h-4 w-4" />
                  Doctor / Hospital Information
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="doctor_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Doctor Name</FormLabel>
                        <FormControl>
                          <Input placeholder="Dr. John Mensah" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="doctor_phone"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Doctor Phone</FormLabel>
                        <FormControl>
                          <Input placeholder="+233 XX XXX XXXX" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="hospital"
                    render={({ field }) => (
                      <FormItem className="md:col-span-2">
                        <FormLabel>Preferred Hospital</FormLabel>
                        <FormControl>
                          <Input placeholder="Hospital name" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-2 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsEditing(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={form.formState.isSubmitting}>
                  {form.formState.isSubmitting ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4 mr-2" />
                      Save Medical Info
                    </>
                  )}
                </Button>
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>
    );
  }

  // Display View
  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between">
        <div>
          <CardTitle className="text-base flex items-center gap-2">
            <Heart className="h-4 w-4" />
            Medical Information
          </CardTitle>
          <CardDescription>
            Health records, allergies, and medical conditions
          </CardDescription>
        </div>
        <Button variant="outline" size="sm" onClick={handleStartEdit}>
          <Edit className="h-4 w-4 mr-2" />
          {hasAnyData ? "Edit" : "Add Info"}
        </Button>
      </CardHeader>
      <CardContent>
        {!hasAnyData ? (
          <div className="text-center py-12">
            <div className="mx-auto w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
              <Heart className="h-7 w-7 text-muted-foreground" />
            </div>
            <h3 className="font-semibold mb-1">No Medical Information</h3>
            <p className="text-muted-foreground mb-4">
              Add blood group, medical conditions, allergies, and medication information.
            </p>
            <Button variant="outline" onClick={handleStartEdit}>
              Add Medical Info
            </Button>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Blood Group */}
            {(student.blood_group || structuredMedical?.blood_group) && (
              <div className="flex items-center gap-4 p-4 rounded-lg bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900">
                <div className="rounded-full bg-red-100 dark:bg-red-900/50 p-3">
                  <Droplet className="h-6 w-6 text-red-600 dark:text-red-400" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Blood Group</p>
                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">
                    {structuredMedical?.blood_group || student.blood_group}
                  </p>
                </div>
              </div>
            )}

            {/* Structured Conditions */}
            {structuredMedical?.conditions && structuredMedical.conditions.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <div className="rounded-lg bg-yellow-100 dark:bg-yellow-900/30 p-1.5">
                    <AlertTriangle className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />
                  </div>
                  <h4 className="font-medium">Medical Conditions</h4>
                </div>
                <div className="space-y-2">
                  {structuredMedical.conditions.map((c, i) => (
                    <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-yellow-50 dark:bg-yellow-950/20 border border-yellow-200 dark:border-yellow-900">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{c.name}</span>
                          {c.severity && (
                            <Badge variant="secondary" className={`text-xs border-0 ${getSeverityColor(c.severity)}`}>
                              {c.severity}
                            </Badge>
                          )}
                        </div>
                        {c.diagnosed_date && (
                          <p className="text-xs text-muted-foreground mt-1">
                            Diagnosed: {c.diagnosed_date}
                          </p>
                        )}
                        {c.notes && (
                          <p className="text-sm text-muted-foreground mt-1">{c.notes}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Legacy text-based conditions (fallback) */}
            {!structuredMedical?.conditions?.length && student.medical_conditions && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <div className="rounded-lg bg-yellow-100 dark:bg-yellow-900/30 p-1.5">
                    <AlertTriangle className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />
                  </div>
                  <h4 className="font-medium">Medical Conditions</h4>
                </div>
                <div className="bg-yellow-50 dark:bg-yellow-950/20 border border-yellow-200 dark:border-yellow-900 rounded-lg p-4">
                  <p className="whitespace-pre-wrap">{student.medical_conditions}</p>
                </div>
              </div>
            )}

            {/* Structured Allergies */}
            {structuredMedical?.allergies && structuredMedical.allergies.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <div className="rounded-lg bg-orange-100 dark:bg-orange-900/30 p-1.5">
                    <AlertCircle className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                  </div>
                  <h4 className="font-medium">Allergies</h4>
                </div>
                <div className="space-y-2">
                  {structuredMedical.allergies.map((a, i) => (
                    <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-orange-50 dark:bg-orange-950/20 border border-orange-200 dark:border-orange-900">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{a.name}</span>
                          {a.severity && (
                            <Badge variant="secondary" className={`text-xs border-0 ${getSeverityColor(a.severity)}`}>
                              {a.severity}
                            </Badge>
                          )}
                        </div>
                        {a.reaction && (
                          <p className="text-sm text-muted-foreground mt-1">
                            Reaction: {a.reaction}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Legacy text-based allergies (fallback) */}
            {!structuredMedical?.allergies?.length && student.allergies && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <div className="rounded-lg bg-orange-100 dark:bg-orange-900/30 p-1.5">
                    <AlertCircle className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                  </div>
                  <h4 className="font-medium">Allergies</h4>
                </div>
                <div className="bg-orange-50 dark:bg-orange-950/20 border border-orange-200 dark:border-orange-900 rounded-lg p-4">
                  <p className="whitespace-pre-wrap">{student.allergies}</p>
                </div>
              </div>
            )}

            {/* Medications */}
            {structuredMedical?.medications && structuredMedical.medications.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <div className="rounded-lg bg-blue-100 dark:bg-blue-900/30 p-1.5">
                    <Pill className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                  </div>
                  <h4 className="font-medium">Current Medications</h4>
                </div>
                <div className="space-y-2">
                  {structuredMedical.medications.map((m, i) => (
                    <div key={i} className="p-3 rounded-lg bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-900">
                      <span className="font-medium">{m.name}</span>
                      {(m.dosage || m.frequency) && (
                        <p className="text-sm text-muted-foreground mt-1">
                          {[m.dosage, m.frequency].filter(Boolean).join(" - ")}
                        </p>
                      )}
                      {m.prescriber && (
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Prescribed by: {m.prescriber}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Emergency Protocol */}
            {structuredMedical?.emergency_protocol && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <div className="rounded-lg bg-red-100 dark:bg-red-900/30 p-1.5">
                    <AlertTriangle className="h-4 w-4 text-red-600 dark:text-red-400" />
                  </div>
                  <h4 className="font-medium">Emergency Protocol</h4>
                </div>
                <div className="bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900 rounded-lg p-4">
                  <p className="whitespace-pre-wrap">{structuredMedical.emergency_protocol}</p>
                </div>
              </div>
            )}

            {/* Doctor Info */}
            {(structuredMedical?.doctor_name || structuredMedical?.hospital) && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <div className="rounded-lg bg-muted p-1.5">
                    <Stethoscope className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <h4 className="font-medium">Doctor / Hospital</h4>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-4 rounded-lg border">
                  {structuredMedical.doctor_name && (
                    <div className="flex items-center gap-2 text-sm">
                      <UserRound className="h-4 w-4 text-muted-foreground" />
                      <span>{structuredMedical.doctor_name}</span>
                    </div>
                  )}
                  {structuredMedical.doctor_phone && (
                    <div className="flex items-center gap-2 text-sm">
                      <Phone className="h-4 w-4 text-muted-foreground" />
                      <a href={`tel:${structuredMedical.doctor_phone}`} className="text-primary hover:underline">
                        {structuredMedical.doctor_phone}
                      </a>
                    </div>
                  )}
                  {structuredMedical.hospital && (
                    <div className="flex items-center gap-2 text-sm md:col-span-2">
                      <Building className="h-4 w-4 text-muted-foreground" />
                      <span>{structuredMedical.hospital}</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
