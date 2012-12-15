from django.contrib.auth.models import User
from django import forms
from django.utils.translation import ugettext_lazy as _
from PIL import Image

from core.models import UserProfile, House, Reservation

from django.contrib.auth.forms import UserCreationForm, UserChangeForm

class ExtendedUserCreationForm(UserCreationForm):
	class Meta:
		model = User
		fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

	def save(self, commit=True):
		# by default the UserCreationForm saves username & password info. here we 
		# override the save method to save the additional data we have gathered. 
		user = super(ExtendedUserCreationForm, self).save(commit=False)
		user.first_name = self.cleaned_data['first_name']
		user.last_name = self.cleaned_data['last_name']
		user.email = self.cleaned_data["email"]
		user.save()
		return user 


class UserProfileForm(forms.ModelForm):     
	''' This form manually incorporates the fields corresponding to the base 
	User model, associated via the UserProfile model via a OneToOne field, so 
	that both models can be updated via the same form. '''

	error_messages = {
		'password_mismatch': _("The two password fields didn't match."),
	}

	# the regex field type automatically validates the value entered against
	# the supplied regex.
	username = forms.RegexField(
		label=_("Username"), max_length=30, regex=r"^[\w.@+-]+$",
		help_text = _("30 characters or fewer. Letters, digits and "
					  "@/./+/-/_ only."),
		error_messages = {
			'invalid': _("This value may contain only letters, numbers and "
						 "@/./+/-/_ characters.")})
	first_name = forms.CharField(label=_('First Name'))
	last_name = forms.CharField(label=_('Last Name'))

	email = forms.EmailField(label=_("E-mail"), max_length=75)
	password1 = forms.CharField(widget=forms.PasswordInput(render_value=False), label=_("New Password"))
	password2 = forms.CharField(widget=forms.PasswordInput(render_value=False), 
		label=_("New Password (again)"))

	class Meta:
		model = UserProfile
		exclude = ['user', 'status']
		fields = ['first_name', 'last_name', 'email', 'username', 'password1', 'password2', 'image', 'bio', 'links']

	def __init__(self, *args, **kwargs):
		super(UserProfileForm, self).__init__(*args, **kwargs)
		# self.instance will always be an instance of UserProfile. if this
		# is an existing object, then populate the initial values. 
		if self.instance.id is not None:
			# initialize the form fields with the existing values from the model.  	
			self.fields['first_name'].initial = self.instance.user.first_name
			self.fields['last_name'].initial = self.instance.user.last_name
			self.fields['username'].initial = self.instance.user.username
			self.fields['email'].initial = self.instance.user.email	

			self.fields['password1'].required = False
			self.fields['password2'].required = False


	def clean_password2(self):
		password1 = self.cleaned_data.get('password1')
		password2 = self.cleaned_data.get('password2')
		if password1 and password2:
			if password1 != password2:
				raise forms.ValidationError(
					self.error_messages['password_mismatch'])
		return password2

	def clean_links(self):
		# validates and formats the urls, returning a string of comma-separated urls
		links = self.cleaned_data['links']
		print 'links is type:'
		print type(links)
		print len(links)
		if len(links) > 0:
			raw_link_list = links.split(',')
			# the UrlField class has some lovely validation code written already.  
			url = forms.URLField()
			cleaned_links = []
			for l in raw_link_list:
				try:
					cleaned = url.clean(l.strip())
					print cleaned 
					cleaned_links.append(cleaned)
				except forms.ValidationError:
					# customize the error raised by UrlField.
					raise forms.ValidationError('At least one of the URLs is not correctly formatted.')
			links = ", ".join(cleaned_links)
		return links

	def clean_image(self):
		img_path = self.cleaned_data['image']
		if img_path is not None:
			# resize or do other intelligent things. 
			pass
		return img_path

	def save(self, commit=True):
		# save the UserProfile (if editing an existing instance, it will be updated)
		profile = super(UserProfileForm, self).save()
		# then update the User model with the values provided
		user = User.objects.get(pk=profile.user.pk)
		if self.cleaned_data.get('email'):
			user.email = self.cleaned_data.get('email')
		if self.cleaned_data.get('username'):
			user.username = self.cleaned_data.get('username')
		if self.cleaned_data['first_name']:
			user.first_name = self.cleaned_data.get('first_name')
		if self.cleaned_data['last_name']:
			user.last_name = self.cleaned_data.get('last_name')
		if self.cleaned_data.get('password2'):
			# set_password hashes the selected password
			user.set_password(self.cleaned_data['password2'])
		user.save()
		return user


class HouseForm(forms.ModelForm):
	class Meta:
		model = House
		exclude = ['admins', 'created', 'updated']

class ReservationForm(forms.ModelForm):
	class Meta:
		model = Reservation
		exclude = ['created', 'updated', 'status', 'user']
		widgets = { 
			'arrive': forms.DateInput(attrs={'class':'datepicker'}),
			'depart': forms.DateInput(attrs={'class':'datepicker'})
		}

	# XXX TODO
	# make sure depart is at least one day after arrive. 

class PaymentForm(forms.Form):
	name = forms.CharField()
	email = forms.EmailField()
	card_number = forms.CharField()
	cvc = forms.IntegerField()
	expiration_month = forms.IntegerField(label='(MM)')
	expiration_year = forms.IntegerField(label='(YYYY)')
	amount = forms.IntegerField(label="Amount in whole dollars")
	comment = forms.CharField(widget=forms.Textarea, required=False, help_text="Optional. If you are\
contributing for someone else, make sure we know who this payment is for.")






