class NetSuiteRecordType:
    CUSTOMER = 'customer'
    EMPLOYEE = 'employee'
    VENDOR = 'vendor'
    
    # NetSuite Item Subtypes
    INVENTORY_ITEM = 'inventoryItem'
    NON_INVENTORY_SALE_ITEM = 'nonInventorySaleItem'
    NON_INVENTORY_RESALE_ITEM = 'nonInventoryResaleItem'
    NON_INVENTORY_PURCHASE_ITEM = 'nonInventoryPurchaseItem'
    SERVICE_SALE_ITEM = 'serviceSaleItem'
    SERVICE_RESALE_ITEM = 'serviceResaleItem'
    SERVICE_PURCHASE_ITEM = 'servicePurchaseItem'
    DESCRIPTION_ITEM = 'descriptionItem'
    DISCOUNT_ITEM = 'discountItem'
    KIT_ITEM = 'kitItem'
    ASSEMBLY_ITEM = 'assemblyItem'
    MARKUP_ITEM = 'markupItem'
    PAYMENT_ITEM = 'paymentItem'
    SUBTOTAL_ITEM = 'subtotalItem'
    ITEM_GROUP = 'itemGroup'

    @classmethod
    def is_valid(cls, record_type: str) -> bool:
        return record_type in [
            cls.CUSTOMER,
            cls.EMPLOYEE,
            cls.VENDOR,
            cls.INVENTORY_ITEM,
            cls.NON_INVENTORY_SALE_ITEM,
            cls.NON_INVENTORY_RESALE_ITEM,
            cls.NON_INVENTORY_PURCHASE_ITEM,
            cls.SERVICE_SALE_ITEM,
            cls.SERVICE_RESALE_ITEM,
            cls.SERVICE_PURCHASE_ITEM,
            cls.DESCRIPTION_ITEM,
            cls.DISCOUNT_ITEM,
            cls.KIT_ITEM,
            cls.ASSEMBLY_ITEM,
            cls.MARKUP_ITEM,
            cls.PAYMENT_ITEM,
            cls.SUBTOTAL_ITEM,
            cls.ITEM_GROUP,
        ]
