from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.schemas.catalog import CategoryOut, CategoryTreeNode, ProductOut
from database import get_db
from database.models import Category, Product

router = APIRouter(tags=["catalog"])

SessionDep = Annotated[AsyncSession, Depends(get_db)]


@router.get("/categories/tree", response_model=list[CategoryTreeNode])
async def categories_tree(session: SessionDep) -> list[CategoryTreeNode]:
    categories = list(
        (
            await session.execute(
                select(Category).order_by(Category.depth_level, Category.name)
            )
        )
        .scalars()
        .all()
    )

    nodes = {c.id: CategoryTreeNode.model_validate(c) for c in categories}
    tree: list[CategoryTreeNode] = []
    for c in categories:
        node = nodes[c.id]
        parent = nodes.get(c.parent_id) if c.parent_id is not None else None
        if parent is not None:
            parent.subcategories.append(node)
        else:
            tree.append(node)
    return tree


@router.get("/categories/{category_id}", response_model=CategoryOut)
async def get_category(
    category_id: int, session: SessionDep
) -> CategoryOut:
    category = (
        (
            await session.execute(
                select(Category).where(Category.id == category_id)
            )
        ).scalar_one_or_none()
    )
    if category is None:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    return CategoryOut.model_validate(category)


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(product_id: int, session: SessionDep) -> ProductOut:
    product = (
        (
            await session.execute(select(Product).where(Product.id == product_id))
        ).scalar_one_or_none()
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return ProductOut.model_validate(product)
