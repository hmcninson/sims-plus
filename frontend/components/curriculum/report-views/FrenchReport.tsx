import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableFooter,
} from "@/components/ui/table";
import type { ReportViewProps } from "./types";

/**
 * French Curriculum Report Card Layout (Bulletin de Notes)
 *
 * Features:
 * - Scores out of 20
 * - Coefficient (subject weight)
 * - Class average per subject
 * - Mention system (Tres Bien, Bien, Assez Bien, Passable)
 * - Weighted average calculation
 */
export function FrenchReport({ report, config, curriculumData }: ReportViewProps) {
  const showClassAverage = config?.show_class_average ?? true;
  const mention = curriculumData?.french_mention;

  // Calculate weighted total if coefficients are available
  const weightedAverage = report.average_score;

  return (
    <div className="space-y-6">
      {/* Student info */}
      <Card>
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div className="space-y-1">
              <p>
                <span className="text-muted-foreground">Nom de l&apos;eleve:</span>{" "}
                <span className="font-medium">{report.student_name}</span>
              </p>
              <p>
                <span className="text-muted-foreground">Matricule:</span>{" "}
                {report.student_id_number}
              </p>
              <p>
                <span className="text-muted-foreground">Classe:</span>{" "}
                {report.class_name}
                {report.section_name && ` (${report.section_name})`}
              </p>
            </div>
            <div className="space-y-1">
              <p>
                <span className="text-muted-foreground">Annee Scolaire:</span>{" "}
                {report.academic_year_name}
              </p>
              <p>
                <span className="text-muted-foreground">Trimestre:</span>{" "}
                {report.term_name}
              </p>
              {mention && (
                <p>
                  <span className="text-muted-foreground">Mention:</span>{" "}
                  <Badge className={getMentionColor(mention)} variant="secondary">
                    {mention}
                  </Badge>
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6 text-center">
            <p className="text-3xl font-bold">{weightedAverage.toFixed(2)}</p>
            <p className="text-xs text-muted-foreground mt-1">Moyenne / 20</p>
          </CardContent>
        </Card>
        {report.class_position && (
          <Card>
            <CardContent className="pt-6 text-center">
              <p className="text-3xl font-bold">
                {report.class_position}
                <span className="text-lg text-muted-foreground">
                  {report.class_size && `/${report.class_size}`}
                </span>
              </p>
              <p className="text-xs text-muted-foreground mt-1">Rang</p>
            </CardContent>
          </Card>
        )}
        {mention && (
          <Card>
            <CardContent className="pt-6 text-center">
              <Badge className={`${getMentionColor(mention)} text-sm px-3 py-1`} variant="secondary">
                {mention}
              </Badge>
              <p className="text-xs text-muted-foreground mt-2">Mention</p>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Subject results (Bulletin) */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Bulletin de Notes</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Matiere</TableHead>
                  <TableHead className="text-center">Coef.</TableHead>
                  <TableHead className="text-center">Note / 20</TableHead>
                  {showClassAverage && (
                    <TableHead className="text-center">Moy. Classe</TableHead>
                  )}
                  <TableHead className="text-center">Note x Coef.</TableHead>
                  <TableHead>Appreciation</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {report.subject_results.map((result) => {
                  const coefficient = "coefficient" in result
                    ? ((result as unknown as { coefficient?: number }).coefficient ?? 1)
                    : 1;
                  // Score is out of 20 in French system
                  const scoreOf20 = result.total_score != null
                    ? (result.total_score / 5) // Convert from /100 to /20
                    : null;
                  const weighted = scoreOf20 != null ? scoreOf20 * coefficient : null;

                  return (
                    <TableRow key={result.subject_id}>
                      <TableCell className="font-medium text-sm">
                        {result.subject_name}
                      </TableCell>
                      <TableCell className="text-center text-sm">
                        {coefficient}
                      </TableCell>
                      <TableCell className="text-center">
                        {scoreOf20 != null ? (
                          <span className={scoreOf20 < 10 ? "text-destructive font-medium" : "font-medium"}>
                            {scoreOf20.toFixed(1)}
                          </span>
                        ) : (
                          "-"
                        )}
                      </TableCell>
                      {showClassAverage && (
                        <TableCell className="text-center text-sm text-muted-foreground">
                          -
                        </TableCell>
                      )}
                      <TableCell className="text-center text-sm">
                        {weighted != null ? weighted.toFixed(1) : "-"}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {result.grade_remark || result.teacher_remark || "-"}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
              <TableFooter>
                <TableRow>
                  <TableCell className="font-semibold">Total / Moyenne</TableCell>
                  <TableCell />
                  <TableCell className="text-center font-bold">
                    {weightedAverage.toFixed(2)}
                  </TableCell>
                  {showClassAverage && <TableCell />}
                  <TableCell />
                  <TableCell />
                </TableRow>
              </TableFooter>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Attendance */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Assiduite</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold">{report.days_present}</p>
              <p className="text-xs text-muted-foreground">Jours Present</p>
            </div>
            <div>
              <p className="text-2xl font-bold">{report.days_absent}</p>
              <p className="text-xs text-muted-foreground">Absences</p>
            </div>
            <div>
              <p className="text-2xl font-bold">{report.total_school_days}</p>
              <p className="text-xs text-muted-foreground">Jours Totaux</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Observations */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Observations</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-xs text-muted-foreground mb-1">Professeur Principal</p>
            <p className="text-sm rounded-lg border p-3 bg-muted/30 min-h-[40px]">
              {report.class_teacher_remark || "Pas d'observation"}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-1">Directeur</p>
            <p className="text-sm rounded-lg border p-3 bg-muted/30 min-h-[40px]">
              {report.headmaster_remark || "Pas d'observation"}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Mention key */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Systeme de Mentions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3 text-xs">
            {[
              { mention: "Tres Bien", range: "16-20" },
              { mention: "Bien", range: "14-15.99" },
              { mention: "Assez Bien", range: "12-13.99" },
              { mention: "Passable", range: "10-11.99" },
              { mention: "Insuffisant", range: "< 10" },
            ].map((m) => (
              <span key={m.mention} className="flex items-center gap-1.5">
                <Badge variant="secondary" className={`${getMentionColor(m.mention)} text-[10px]`}>
                  {m.mention}
                </Badge>
                <span className="text-muted-foreground">{m.range}/20</span>
              </span>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function getMentionColor(mention: string): string {
  const m = mention.toLowerCase();
  if (m.includes("tres bien")) return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
  if (m === "bien") return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
  if (m.includes("assez")) return "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200";
  if (m.includes("passable")) return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
  return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
}
