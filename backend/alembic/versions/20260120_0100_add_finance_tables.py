"""Add finance tables for fee structures, invoices, payments, and scholarships.

Revision ID: 20260120_0100
Revises: 20260112_0300
Create Date: 2026-01-20 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260120_0100"
down_revision: Union[str, None] = "20260112_0300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create finance tables: fee_structures, fee_items, invoices, invoice_items, payments, scholarships, student_scholarships, scholarship_applications."""

    # Create enums
    invoice_status_enum = postgresql.ENUM(
        'draft', 'issued', 'partial', 'paid', 'overdue', 'cancelled',
        name='invoicestatus', create_type=False
    )
    invoice_status_enum.create(op.get_bind(), checkfirst=True)

    payment_method_enum = postgresql.ENUM(
        'cash', 'momo_mtn', 'momo_vodafone', 'momo_airteltigo', 'bank_transfer', 'cheque', 'card', 'other',
        name='paymentmethod', create_type=False
    )
    payment_method_enum.create(op.get_bind(), checkfirst=True)

    payment_status_enum = postgresql.ENUM(
        'pending', 'completed', 'failed', 'refunded', 'cancelled',
        name='paymentstatus', create_type=False
    )
    payment_status_enum.create(op.get_bind(), checkfirst=True)

    scholarship_type_enum = postgresql.ENUM(
        'full', 'partial', 'merit', 'need_based', 'athletic', 'special',
        name='scholarshiptype', create_type=False
    )
    scholarship_type_enum.create(op.get_bind(), checkfirst=True)

    coverage_type_enum = postgresql.ENUM(
        'percentage', 'fixed_amount',
        name='coveragetype', create_type=False
    )
    coverage_type_enum.create(op.get_bind(), checkfirst=True)

    scholarship_status_enum = postgresql.ENUM(
        'active', 'suspended', 'revoked', 'expired',
        name='scholarshipstatus', create_type=False
    )
    scholarship_status_enum.create(op.get_bind(), checkfirst=True)

    application_status_enum = postgresql.ENUM(
        'pending', 'under_review', 'approved', 'rejected',
        name='applicationstatus', create_type=False
    )
    application_status_enum.create(op.get_bind(), checkfirst=True)

    # ========================
    # fee_structures table
    # ========================
    op.create_table(
        'fee_structures',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('school_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False, comment='Fee structure name, e.g., Term 1 Fees 2025/2026'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('academic_year_id', sa.UUID(), nullable=True),
        sa.Column('term_id', sa.UUID(), nullable=True),
        sa.Column('class_id', sa.UUID(), nullable=True, comment='Optional: applies to specific class'),
        sa.Column('level', sa.String(20), nullable=True, comment='Optional: applies to class level (jhs_1, shs_2, etc.)'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        # Constraints
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['term_id'], ['terms.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_fee_structures_tenant_id', 'fee_structures', ['tenant_id'])
    op.create_index('ix_fee_structures_school_id', 'fee_structures', ['school_id'])
    op.create_index('ix_fee_structures_academic_year_id', 'fee_structures', ['academic_year_id'])
    op.create_index('ix_fee_structures_is_active', 'fee_structures', ['is_active'])

    # ========================
    # fee_items table
    # ========================
    op.create_table(
        'fee_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('fee_structure_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False, comment='Fee item name, e.g., Tuition, Examination Fee'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('is_optional', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('sequence', sa.Integer(), nullable=False, server_default='0', comment='Display order'),
        # Constraints
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['fee_structure_id'], ['fee_structures.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_fee_items_tenant_id', 'fee_items', ['tenant_id'])
    op.create_index('ix_fee_items_fee_structure_id', 'fee_items', ['fee_structure_id'])

    # ========================
    # invoices table
    # ========================
    op.create_table(
        'invoices',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('school_id', sa.UUID(), nullable=False),
        sa.Column('invoice_number', sa.String(50), nullable=False, comment='Auto-generated invoice number'),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('fee_structure_id', sa.UUID(), nullable=True),
        sa.Column('academic_year_id', sa.UUID(), nullable=False),
        sa.Column('term_id', sa.UUID(), nullable=False),
        # Amounts
        sa.Column('subtotal', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('discount_amount', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('scholarship_discount', sa.Numeric(12, 2), nullable=False, server_default='0.00', comment='Scholarship-based discount'),
        sa.Column('tax_amount', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('total_amount', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('amount_paid', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        # Status and dates
        sa.Column('status', invoice_status_enum, nullable=False, server_default='draft'),
        sa.Column('issue_date', sa.Date(), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('currency', sa.String(3), nullable=False, server_default='GHS'),
        sa.Column('notes', sa.Text(), nullable=True),
        # Audit
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('issued_by', sa.UUID(), nullable=True),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_by', sa.UUID(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancel_reason', sa.Text(), nullable=True),
        # Constraints
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['fee_structure_id'], ['fee_structures.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['term_id'], ['terms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['issued_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['cancelled_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'invoice_number', name='uq_invoice_number'),
    )
    op.create_index('ix_invoices_tenant_id', 'invoices', ['tenant_id'])
    op.create_index('ix_invoices_school_id', 'invoices', ['school_id'])
    op.create_index('ix_invoices_student_id', 'invoices', ['student_id'])
    op.create_index('ix_invoices_academic_year_id', 'invoices', ['academic_year_id'])
    op.create_index('ix_invoices_term_id', 'invoices', ['term_id'])
    op.create_index('ix_invoices_status', 'invoices', ['status'])
    op.create_index('ix_invoices_due_date', 'invoices', ['due_date'])

    # ========================
    # invoice_items table
    # ========================
    op.create_table(
        'invoice_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('invoice_id', sa.UUID(), nullable=False),
        sa.Column('fee_item_id', sa.UUID(), nullable=True, comment='Reference to fee item if applicable'),
        sa.Column('description', sa.String(255), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('unit_price', sa.Numeric(12, 2), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        # Constraints
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['fee_item_id'], ['fee_items.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_invoice_items_tenant_id', 'invoice_items', ['tenant_id'])
    op.create_index('ix_invoice_items_invoice_id', 'invoice_items', ['invoice_id'])

    # ========================
    # payments table
    # ========================
    op.create_table(
        'payments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('school_id', sa.UUID(), nullable=False),
        sa.Column('receipt_number', sa.String(50), nullable=False, comment='Auto-generated receipt number'),
        sa.Column('invoice_id', sa.UUID(), nullable=True),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='GHS'),
        # Payment method details
        sa.Column('payment_method', payment_method_enum, nullable=False),
        sa.Column('momo_phone', sa.String(20), nullable=True, comment='Mobile money phone number'),
        sa.Column('momo_transaction_id', sa.String(100), nullable=True, comment='Mobile money transaction ID'),
        sa.Column('momo_provider', sa.String(20), nullable=True, comment='MTN, Vodafone, AirtelTigo'),
        sa.Column('bank_name', sa.String(100), nullable=True),
        sa.Column('bank_reference', sa.String(100), nullable=True),
        sa.Column('cheque_number', sa.String(50), nullable=True),
        # Payer info
        sa.Column('payer_name', sa.String(100), nullable=True),
        sa.Column('payer_phone', sa.String(20), nullable=True),
        sa.Column('payer_email', sa.String(255), nullable=True),
        # Status
        sa.Column('status', payment_status_enum, nullable=False, server_default='completed'),
        sa.Column('payment_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        # Void info
        sa.Column('is_voided', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('voided_by', sa.UUID(), nullable=True),
        sa.Column('voided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('void_reason', sa.Text(), nullable=True),
        # Audit
        sa.Column('recorded_by', sa.UUID(), nullable=True),
        # Constraints
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['voided_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['recorded_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'receipt_number', name='uq_receipt_number'),
    )
    op.create_index('ix_payments_tenant_id', 'payments', ['tenant_id'])
    op.create_index('ix_payments_school_id', 'payments', ['school_id'])
    op.create_index('ix_payments_student_id', 'payments', ['student_id'])
    op.create_index('ix_payments_invoice_id', 'payments', ['invoice_id'])
    op.create_index('ix_payments_status', 'payments', ['status'])
    op.create_index('ix_payments_payment_date', 'payments', ['payment_date'])

    # ========================
    # scholarships table
    # ========================
    op.create_table(
        'scholarships',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('school_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False, comment='Scholarship name, e.g., Academic Excellence Award'),
        sa.Column('code', sa.String(20), nullable=False, comment='Unique code, e.g., AEA-2026'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('scholarship_type', scholarship_type_enum, nullable=False),
        sa.Column('coverage_type', coverage_type_enum, nullable=False),
        sa.Column('coverage_value', sa.Numeric(12, 2), nullable=False, comment='Percentage (0-100) or fixed GHS amount'),
        sa.Column('applicable_fees', postgresql.JSONB(), nullable=True, comment='Which fee items it covers: ["tuition", "all"] or specific IDs'),
        sa.Column('max_recipients', sa.Integer(), nullable=True, comment='Optional: limit number of awards'),
        sa.Column('academic_year_id', sa.UUID(), nullable=True),
        sa.Column('eligibility_criteria', postgresql.JSONB(), nullable=True, comment='{"min_gpa": 3.5, "max_income": 5000}'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        # Audit
        sa.Column('created_by', sa.UUID(), nullable=True),
        # Constraints
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'code', name='uq_scholarship_code'),
    )
    op.create_index('ix_scholarships_tenant_id', 'scholarships', ['tenant_id'])
    op.create_index('ix_scholarships_school_id', 'scholarships', ['school_id'])
    op.create_index('ix_scholarships_academic_year_id', 'scholarships', ['academic_year_id'])
    op.create_index('ix_scholarships_is_active', 'scholarships', ['is_active'])

    # ========================
    # student_scholarships table
    # ========================
    op.create_table(
        'student_scholarships',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('scholarship_id', sa.UUID(), nullable=False),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('academic_year_id', sa.UUID(), nullable=False),
        sa.Column('awarded_by', sa.UUID(), nullable=True),
        sa.Column('awarded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', scholarship_status_enum, nullable=False, server_default='active'),
        sa.Column('effective_from', sa.Date(), nullable=False),
        sa.Column('effective_to', sa.Date(), nullable=True, comment='NULL = until end of academic year'),
        sa.Column('coverage_override', sa.Numeric(12, 2), nullable=True, comment='Override default coverage if needed'),
        sa.Column('notes', sa.Text(), nullable=True),
        # Revocation info
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_by', sa.UUID(), nullable=True),
        sa.Column('revoke_reason', sa.Text(), nullable=True),
        # Constraints
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['scholarship_id'], ['scholarships.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['awarded_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['revoked_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_student_scholarships_tenant_id', 'student_scholarships', ['tenant_id'])
    op.create_index('ix_student_scholarships_student_id', 'student_scholarships', ['student_id'])
    op.create_index('ix_student_scholarships_scholarship_id', 'student_scholarships', ['scholarship_id'])
    op.create_index('ix_student_scholarships_status', 'student_scholarships', ['status'])
    # Unique constraint: one scholarship per student per academic year
    op.create_index(
        'uq_student_scholarship_unique',
        'student_scholarships',
        ['tenant_id', 'scholarship_id', 'student_id', 'academic_year_id'],
        unique=True
    )

    # ========================
    # scholarship_applications table
    # ========================
    op.create_table(
        'scholarship_applications',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('scholarship_id', sa.UUID(), nullable=False),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('academic_year_id', sa.UUID(), nullable=False),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', application_status_enum, nullable=False, server_default='pending'),
        sa.Column('supporting_documents', postgresql.JSONB(), nullable=True, comment='[{name, url, type}]'),
        sa.Column('application_notes', sa.Text(), nullable=True),
        # Review info
        sa.Column('reviewer_id', sa.UUID(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewer_notes', sa.Text(), nullable=True),
        # Constraints
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['scholarship_id'], ['scholarships.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_scholarship_applications_tenant_id', 'scholarship_applications', ['tenant_id'])
    op.create_index('ix_scholarship_applications_student_id', 'scholarship_applications', ['student_id'])
    op.create_index('ix_scholarship_applications_scholarship_id', 'scholarship_applications', ['scholarship_id'])
    op.create_index('ix_scholarship_applications_status', 'scholarship_applications', ['status'])


def downgrade() -> None:
    """Drop finance tables."""
    # Drop tables in reverse order of creation
    op.drop_table('scholarship_applications')
    op.drop_table('student_scholarships')
    op.drop_table('scholarships')
    op.drop_table('payments')
    op.drop_table('invoice_items')
    op.drop_table('invoices')
    op.drop_table('fee_items')
    op.drop_table('fee_structures')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS applicationstatus')
    op.execute('DROP TYPE IF EXISTS scholarshipstatus')
    op.execute('DROP TYPE IF EXISTS coveragetype')
    op.execute('DROP TYPE IF EXISTS scholarshiptype')
    op.execute('DROP TYPE IF EXISTS paymentstatus')
    op.execute('DROP TYPE IF EXISTS paymentmethod')
    op.execute('DROP TYPE IF EXISTS invoicestatus')
