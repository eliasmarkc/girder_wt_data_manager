#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

from bson import objectid
from girder.constants import AccessType
from girder.models.folder import Folder
from girder.models.item import Item
from girder.models.model_base import AccessControlledModel, AccessException
from lock import Lock
from girder import events

class Session(AccessControlledModel):
    def initialize(self):
        self.name = 'session'
        self.exposeFields(level = AccessType.READ, fields = {'_id', 'status', 'ownerId', 'dataSet', 'error'})
        self.folderModel = Folder()
        self.itemModel = Item()
        self.lockModel = Lock()

    def validate(self, session):
        return session

    def list(self, user, limit = 0, offset = 0, sort = None):
        """
        List a page of containers for a given user.

        :param user: The user who owns the job.
        :type user: dict or None
        :param limit: The page limit.
        :param offset: The page offset
        :param sort: The sort field.
        """
        userId = user['_id'] if user else None
        cursor = self.find({'ownerId': userId}, sort = sort)

        for r in self.filterResultsByPermission(cursor = cursor, user = user,
            level = AccessType.READ, limit = limit, offset = offset):
            yield r

    def createSession(self, user, dataSet = None):
        """
        Create a new session.

        :param user: The user creating the job.
        :type user: dict or None
        :param dataSet: The initial dataSet associated with this session
        :type dataSet: dict
        """

        session = {
            '_id': objectid.ObjectId(),
            'ownerId': user['_id'],
            'dataSet': dataSet
        }

        self.setUserAccess(session, user = user, level = AccessType.ADMIN)

        session = self.save(session)

        print 'Session ' + str(session['_id']) + ' created'
        events.trigger('dm.sessionCreated', info = session)

        return session

    def checkOwnership(self, user, session):
        if 'ownerId' in session:
            ownerId = session['ownerId']
        else:
            ownerId = session['userId']
        if ownerId != user['_id']:
            raise AccessException('Current user is not the session owner')


    def deleteSession(self, user, session):
        self.checkOwnership(user, session)
        self.remove(session)
        events.trigger('dm.sessionDeleted', info=session)

    def addFilesToSession(self, user, session, dataSet):
        """
        Add some files to a session.

        :param user: The user requesting the operation
        :param session: The session to which to add the files
        :param dataSet: A data set containing the files to be added
        """
        self.checkOwnership(user, session)

        session['dataSet'].addFiles(dataSet)
        self.save(session)

        return session

    def removeFilesFromSession(self, user, session, dataSet):
        """
        Remove files from a session.

        :param user: The user requesting the operation
        :param session: The session from which the files are to be removed
        :param dataSet: A data set containing the files to be removed
        """
        self.checkOwnership(user, session)

        session['dataSet'].removeFiles(dataSet)
        self.save(session)

        return session

    def getObject(self, user, session, path, children):
        self.checkOwnership(user, session)

        pathEls = self.splitPath(path)

        crtObj = session
        for item in pathEls:
            crtObj = self.findObject(crtObj, item)
        if children:
            return {
                'object': crtObj,
                'children': self.listChildren(crtObj)
            }
        else:
            return {
                'object': crtObj
            }

    def findObject(self, container, name):
        if 'dataSet' in container:
            return self.findObjectInSession(container, name)
        else:
            return self.findObjectInFolder(container, name)

    def findObjectInSession(self, session, name):
        sname = "/" + name

        for obj in session['dataSet']:
            if obj['mountPath'] == sname:
                return self.loadObject(str(obj['itemId']))
        raise LookupError("No such object: " + name)

    def loadObject(self, id):
        item = self.folderModel.load(id, level=AccessType.READ)
        if item != None:
            item['type'] = 'folder'
            return item
        else:
            item = self.itemModel.load(id, level=AccessType.READ)
            if item != None:
                item['type'] = 'file'
                return item
        raise LookupError("No such object: " + id)

    def listChildren(self, item):
        l = list(self.folderModel.childFolders(item, 'folder'))
        l.extend(self.folderModel.childItems(item))
        return l

    def findObjectInFolder(self, container, name):
        parentId = container['_id']

        item = self.folderModel.findOne(query = {'parentId': parentId, 'name': name}, level=AccessType.READ)
        if item != None:
            item['type'] = 'folder'
            return item
        item = self.itemModel.findOne(query={'folderId': parentId, 'name': name}, level=AccessType.READ)
        if item != None:
            item['type'] = 'file'
            return item
        raise LookupError('No such object: ' + name)

    def splitPath(self, path):
        l = []
        while path != '' and path != '/':
            (path, tail) = os.path.split(path)
            l.insert(0, tail)
        return l

    def getPrivateStoragePath(self, itemId):
        item = self.itemModel.findOne(query = {'_id': itemId}, fields = ['dm.psPath'])
        return item['dm.psPath']