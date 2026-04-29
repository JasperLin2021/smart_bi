import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class CatalogTests(unittest.TestCase):
    def _db(self):
        from app.db.base_class import Base
        from app.models.catalog import DataAsset
        from app.models.organization import Organization  # noqa: F401

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=[DataAsset.__table__])
        return sessionmaker(bind=engine)()

    def test_regular_user_sees_published_same_org_assets_and_owned_drafts(self):
        from app.api.catalog import list_assets
        from app.models.catalog import DataAsset

        db = self._db()
        db.add_all(
            [
                DataAsset(asset_type="metric", name="良率", org_id=1, owner_id=20, status="published"),
                DataAsset(asset_type="dashboard", name="我的草稿", org_id=1, owner_id=10, status="draft"),
                DataAsset(asset_type="table", name="其他组织资产", org_id=2, owner_id=30, status="published"),
                DataAsset(asset_type="metric", name="他人草稿", org_id=1, owner_id=20, status="draft"),
            ]
        )
        db.commit()

        result = list_assets(db=db, current_user=SimpleNamespace(id=10, role="user", org_id=1))

        self.assertEqual([item.name for item in result["items"]], ["我的草稿", "良率"])

    def test_org_admin_can_publish_asset_in_own_org(self):
        from app.api.catalog import update_asset_status
        from app.models.catalog import DataAsset
        from app.schemas.catalog import DataAssetStatusUpdate

        db = self._db()
        asset = DataAsset(asset_type="metric", name="良率", org_id=1, owner_id=20, status="draft")
        db.add(asset)
        db.commit()
        db.refresh(asset)

        result = update_asset_status(
            asset.id,
            DataAssetStatusUpdate(status="published"),
            db=db,
            current_user=SimpleNamespace(id=11, role="org_admin", org_id=1),
        )

        self.assertEqual(result.status, "published")


if __name__ == "__main__":
    unittest.main()
