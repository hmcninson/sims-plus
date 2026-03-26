"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DollarSign, Gift, MinusCircle, Receipt, Building2 } from "lucide-react";

import { SalaryGradesTab } from "@/components/payroll/SalaryGradesTab";
import { AllowanceTypesTab } from "@/components/payroll/AllowanceTypesTab";
import { DeductionTypesTab } from "@/components/payroll/DeductionTypesTab";
import { TaxBracketsTab } from "@/components/payroll/TaxBracketsTab";
import { BankFileConfigsTab } from "@/components/payroll/BankFileConfigsTab";

export default function PayrollSettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Payroll Settings</h1>
        <p className="text-muted-foreground">
          Configure salary grades, allowances, deductions, tax brackets, and bank file formats
        </p>
      </div>

      <Tabs defaultValue="salary-grades" className="space-y-4">
        <TabsList className="flex w-full flex-wrap gap-1 h-auto p-1">
          <TabsTrigger value="salary-grades" className="flex items-center gap-1.5">
            <DollarSign className="h-4 w-4" />
            <span className="hidden sm:inline">Salary Grades</span>
            <span className="sm:hidden">Grades</span>
          </TabsTrigger>
          <TabsTrigger value="allowances" className="flex items-center gap-1.5">
            <Gift className="h-4 w-4" />
            <span className="hidden sm:inline">Allowances</span>
            <span className="sm:hidden">Allow.</span>
          </TabsTrigger>
          <TabsTrigger value="deductions" className="flex items-center gap-1.5">
            <MinusCircle className="h-4 w-4" />
            <span className="hidden sm:inline">Deductions</span>
            <span className="sm:hidden">Deduct.</span>
          </TabsTrigger>
          <TabsTrigger value="tax-brackets" className="flex items-center gap-1.5">
            <Receipt className="h-4 w-4" />
            <span className="hidden sm:inline">Tax Brackets</span>
            <span className="sm:hidden">Tax</span>
          </TabsTrigger>
          <TabsTrigger value="bank-files" className="flex items-center gap-1.5">
            <Building2 className="h-4 w-4" />
            <span className="hidden sm:inline">Bank Files</span>
            <span className="sm:hidden">Bank</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="salary-grades">
          <SalaryGradesTab />
        </TabsContent>
        <TabsContent value="allowances">
          <AllowanceTypesTab />
        </TabsContent>
        <TabsContent value="deductions">
          <DeductionTypesTab />
        </TabsContent>
        <TabsContent value="tax-brackets">
          <TaxBracketsTab />
        </TabsContent>
        <TabsContent value="bank-files">
          <BankFileConfigsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
