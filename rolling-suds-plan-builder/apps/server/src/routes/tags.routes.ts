import { Router } from 'express';
import { createTag, listTags } from '../controllers/tag.controller.js';
import { requireAuth } from '../middleware/auth.js';

const router = Router();
router.get('/', requireAuth, listTags);
router.post('/', requireAuth, createTag);
export default router;
