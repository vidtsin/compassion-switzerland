# -*- coding: utf-8 -*-
##############################################################################
#
#    Author: Emanuel Cino. Copyright Compassion Suisse
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from openerp.osv.orm import Model
from openerp.osv import fields, osv
from openerp.tools.translate import _
import requests
import pdb
import datetime


SERVER_URL = 'https://test.services.compassion.ch:443/rest/openerp/'


class gmc_message_pool(Model):
    """ Pool of messages exchanged between Compassion CH and GMC. """
    _name = 'gmc.message.pool'

    _columns = {
        'date': fields.date(_('Message Date'), required=True, readonly=True),
        'action_id': fields.many2one('gmc.action',_('GMC Message'),
                                  ondelete="restrict", required=True,
                                  readonly=True),
        'send_date': fields.date(_('Date Sent to GMC'), readonly=True),
        'state': fields.selection(
            [('pending', _('Pending')),
             ('sent', _('Sent'))],
            _('State'), readonly=True
        ),
        'object_id': fields.integer(_('Referrenced Object Id')),
        'incoming_key': fields.char(_('Object Reference'), size=9,
                                    help=_("In case of incoming message, \
                                            contains the reference of the \
                                            child or the project that will \
                                            be created/modified.")),
    }
    
    def process_messages(self, cr, uid, ids, context=None):
        """ Process given messages in pool. """
        success_ids = []
        for message = self.browse(cr, uid, ids, context=context):
            if message.state == 'pending':
                message_args = {'object_ref':message.incoming_key}
                if self.pool.get('gmc.action').execute(cr, uid, message.action_id.id, message.object_id, message_args, context=context):
                    success_ids.append(message.id)
                    
        if success_ids:
            self.write(cr, uid, success_ids, {'state':'sent','send_date':datetime.date.today()}, context=context)
                    
gmc_message_pool()


class gmc_action(Model):
    _description = """ 
    A GMC Action defines what has to be done for a specific OffRamp
    message of the Compassion International specification.
    
    A GMC Action can be originated either from an incoming or an outgoing
    message read from the GMC Message Pool class.
    
    Incoming actions :
        - Execute a method of a given OpenERP Object.
        - Each incoming action should map to some code to execute defined
          in the _perform_incoming_action() method.
        
    Outgoing actions :
        - Execute a method by calling Buckhill's middleware.
    """
    _name = 'gmc.action'
    
    def _get_message_types(self, cr, uid, context=None):
        res = self._get_incoming_message_types() + self._get_outgoing_message_types()
        # Extend with methods for both incoming and outgoing messages.
        return res.append(
            ('update', 'Update Object'),
        )
        
    def _get_incoming_message_types(self):
        """ Incoming message types calling specific method on an object. 
            The method should exist on the given model.
        """
        return [
            ('allocate','Allocate new Child'),
            ('deallocate', 'Deallocate Child'),
            ('depart', 'Depart Child'),
        ]
    
    def _get_outgoing_message_types(self):
        """ Outgoing messages sent to the middleware. """
        return [
            ('create','Create object'),
        ]
    
    
    _columns = {
        'direction': fields.selection(
            (('in',_('Incoming Message')),
             ('out',_('Outgoing Message')),
            ),
            _('Message Direction'), required=True
        ),
        'name': fields.char(_('GMC Message'), size=20, required=True),
        'model': fields.char('OSV Model', size=30),
        'type': fields.selection(_get_message_types, _('Action Type'), required=True),
    }
    
    
    def execute(self, cr, uid, id, object_id, args={}, context=None):
        """ Executes the action on the given object_id. 
        
            Args:
                - id: id of the action to be executed.
                - object_id: for incoming messages, object on which to perform the action.
                             for outgoing messages, object from which to read data.
                - args (dict): for incoming messages, optional arguments to be passed in the executed method.
        """
        action = self.browse(cr, uid, id, context=context):

        if action.direction == 'in':
            return self._perform_incoming_action(cr, uid, action, object_id, args=args, context=context)
        elif action.direction == 'out':
            return self._perform_outgoing_action()
        else:
            raise NotImplementedError
            
            
    def create(self, cr, uid, values, context={}):
        direction = values.get('direction', False)
        model = values.get('model', False)
        action_type = values.get('type', False)
        
        if self._validate_action(direction, model, action_type):
            return super(gmc_action, self).create(cr, uid, values, context=context)
        else:
            raise osv.except_osv(_("Invalid action. Creation aborted."))
                
                
    def _perform_incoming_action(self, cr, uid, action, object_id, args={}, context=None):
        """ This method defines what has to be done for each incoming message type. """
        res = False
        model_obj = self.pool.get(action.model)
        if action.type == 'allocate':
            ref = args['object_ref']
            res = model_obj.allocate(cr, uid, ref, context=context)
        elif action.type in ('deallocate', 'depart', 'update'):
            res = getattr(model_obj, action.type)(cr, uid, object_id, context=context)
        else:
            raise osv.except_osv("No implementation found for method '%s'." % (action.type))
            
        return res
    
    def _perform_outgoing_action(self, object_id, action_type):
        """ Process an outgoing message by sending it to the middleware. """
        return True
    
    
    def _validate_action(self, direction, model, action_type, context=None):
        """ Test if the action can be performed on given model. """
        if direction and model and action_type:
            if direction == 'in':
                model_obj = self.pool.get(model)
                return hasattr(model_obj, action_type)
            elif direction == 'out':
                return True
        
        return False
        
gmc_action()